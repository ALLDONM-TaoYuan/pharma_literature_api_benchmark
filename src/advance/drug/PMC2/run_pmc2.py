"""PMC2 collector: one round per alias as in ES2/EPMC2; PMC2 copies it and takes the alias table from this board's ES2."""
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("drug", "PMC2")


import main as project
from config import PMC_query, settings
import query as variant

TABLES = ("approved drugs.xlsx", "unapproved drugs.xlsx")
ROUND_DELAY = 0.4
DUAL = False
SIZE = settings.TOP_N
DRY_RUN = False


def search_ids(term: str, retmax: int):
    params = project.ncbi_params(
        {"term": term, "retmax": retmax, "retmode": "json", "sort": "relevance"}
    )
    status, payload = project.call_api(
        settings.PMC_URL, params, method="post",
        validate=lambda data: "esearchresult" in data,
        retry_times=5, retry_wait=8,
    )
    search = payload.get("esearchresult", {})
    ids = [str(value) for value in search.get("idlist", [])]
    return project.to_int(search.get("count")), ids, status


def cited_ids(epmc_term: str, size: int):
    from config import Europe_PMC_query
    params = Europe_PMC_query.build_params(
        epmc_term + " AND SRC:PMC",
        sort=getattr(settings, "EUROPE_PMC_CITED_SORT", "CITED desc"),
        page_size=size,
    )
    _, payload = project.call_api(
        settings.EUROPE_PMC_URL, params, validate=lambda data: "hitCount" in data,
        retry_times=4, retry_wait=10,
    )
    out = []
    for item in payload.get("resultList", {}).get("result", []):
        pmcid = str(item.get("pmcid") or "").strip().upper().replace("PMC", "")
        if pmcid:
            out.append(pmcid)
    return out


def priors_of(name: str) -> dict:
    out = {}
    aliases = getattr(variant, "aliases_of", None)
    if aliases:
        out["aliases"] = aliases(name)
    base = getattr(variant, "base_forms", None)
    if base:
        out["base_forms"] = base(name)
    info_groups = getattr(variant, "info_groups", None)
    if info_groups:
        out["info_groups"] = info_groups(name)
    return out


def fulltext_summary(results: list) -> dict:
    selected = len(results)
    full = [r for r in results if r.get("content_type") == "full_text"]
    chars = [len(str(r.get("content") or "")) for r in results]
    return {
        "selected": selected,
        "full_text_count": len(full),
        "abstract_only_count": len([r for r in results if r.get("content_type") == "abstract_only"]),
        "metadata_only_count": len([r for r in results if r.get("content_type") == "metadata_only"]),
        "coverage_of_selected": round(len(full) / selected, 4) if selected else 0.0,
        "avg_content_chars": round(sum(chars) / selected) if selected else 0,
        "fulltext_top_n": settings.FULLTEXT_TOP_N,
    }


def out_path(info: dict, name: str, dimension: str, is_competitor: bool) -> Path:
    base = DATA / "output" / project.safe_name(info["drug"])
    if is_competitor:
        base = base / "competitors" / project.safe_name(name)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{project.safe_name(name)}_{dimension}.json"


def run_one(info: dict, dimension: str, name: str, is_competitor: bool) -> dict:
    unit = project.build_unit(info, dimension, name, is_competitor)
    groups = PMC_query.keyword_groups(dimension)
    local = project.with_keyword_groups(unit, groups)
    rounds = variant.build_round_queries(name, dimension, groups)
    if DRY_RUN:
        for item in rounds:
            pass
        return {}

    request = {"url": settings.PMC_URL, "method": "POST (form)", "params": {"search rounds": rounds}}
    try:
        buckets, seen, total_sum, status, meta = [], set(), 0, None, []
        for item in rounds:
            total, ids, status = search_ids(item["pmc_term"], SIZE)
            time.sleep(ROUND_DELAY)
            cited = []
            if DUAL and item.get("epmc_term"):
                try:
                    cited = cited_ids(item["epmc_term"], SIZE)
                except Exception:
                    cited = []
            ordered = list(dict.fromkeys(cited + ids))
            total_sum += total
            meta.append({"label": item["label"], "pmc_term": item["pmc_term"],
                         "hitCount": total, "ids": len(ordered)})
            bucket = [uid for uid in ordered if uid not in seen]
            seen.update(bucket)
            buckets.append(bucket)

        merged, cursor = [], 0
        while len(merged) < settings.TOP_N and any(cursor < len(b) for b in buckets):
            for bucket in buckets:
                if cursor < len(bucket) and len(merged) < settings.TOP_N:
                    merged.append(bucket[cursor])
            cursor += 1

        results = project.pmc_items(merged, local) if merged else []
        record = project.build_record(local, variant.MODE, request, status, total_sum, results)
        record["variant"] = variant.MODE
        record["rounds"] = meta
        record["merged_unique"] = len(seen)
        record["priors"] = priors_of(name)
        record["fulltext"] = fulltext_summary(results)
    except Exception as exc:
        record = project.build_record(local, variant.MODE, request, None, 0, [], error=f"unexpected error: {exc}")
    project.save_json(out_path(info, name, dimension, is_competitor), record)
    return record


def main() -> int:
    global DRY_RUN
    raw = sys.argv[1:]
    DRY_RUN = "--dry-run" in raw
    dims = list(variant.DIMENSIONS)
    if "--dimension" in raw:
        idx = raw.index("--dimension")
        if idx + 1 < len(raw):
            dims = [raw[idx + 1]]
        raw = raw[:idx] + raw[idx + 2:]
    argv = [arg for arg in raw if not arg.startswith("-")]
    total_objects = 0
    for table_name in TABLES:
        objects = project.read_drug_table(DATA.parent / table_name)
        if argv:
            objects = [info for info in objects if info["drug"] == argv[0]]
        total_objects += len(objects)

        run_table_objects(objects, dims, table_name)

    return 0


def run_table_objects(objects, dims, table_name):
    for info in objects:
        entries, started = [], time.time()
        for dimension in dims:
            for name, is_competitor in [(info["drug"], False)] + [(c, True) for c in info.get("competitors", [])]:
                record = run_one(info, dimension, name, is_competitor)
                record.get("fulltext") or {}

        if DRY_RUN:
            continue
        log = {
            "variant": variant.MODE, "drug": info["drug"],
            "sheet": info.get("sheet", ""), "table": table_name,
            "mode": f"{variant.MODE}-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "dimensions": list(variant.DIMENSIONS),
            "priors": priors_of(info["drug"]),
            "units": entries,
        }
        log_path = DATA / "output" / project.safe_name(info["drug"]) / "run_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        project.save_json(log_path, log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
