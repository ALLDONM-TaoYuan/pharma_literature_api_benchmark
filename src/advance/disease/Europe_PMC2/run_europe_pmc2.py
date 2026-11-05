"""Europe_PMC2 collector: ES2 first pulls the various spellings of a disease from the info table (English name, abbreviation, synonyms, gene name),"""
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
DATA = variant_data("disease", "Europe_PMC2")


import main as project
from config import settings
import query as variant

TABLE = "disease.xlsx"
ROUND_DELAY = 1.0


def fetch_round(query_text: str):
    params = {
        "query": query_text,
        "format": "json",
        "resultType": "core",
        "pageSize": settings.TOP_N,
    }

    status, payload = project.call_api(
        settings.EUROPE_PMC_URL, params,
        validate=lambda data: "hitCount" in data,
        retry_times=8, retry_wait=15,
    )
    total = project.to_int(payload.get("hitCount"))
    items = payload.get("resultList", {}).get("result", [])[: settings.TOP_N]
    return total, items, status, params


def priors_of(disease: str) -> dict:
    out = {}
    aliases = getattr(variant, "aliases_of", None)
    if aliases:
        out["aliases"] = aliases(disease)
    elif hasattr(variant, "base_forms"):
        out["base_forms"] = variant.base_forms(disease)
    ladder = getattr(variant, "ladder_forms", None)
    if ladder:
        out["ladder_forms"] = ladder(disease)
    info_groups = getattr(variant, "info_groups", None)
    if info_groups:
        out["info_groups"] = info_groups(disease)
    return out


def fulltext_summary(results: list, top_n: int = None) -> dict:
    selected = len(results)
    full = [r for r in results if r.get("content_type") == "full_text"]
    abstract = [r for r in results if r.get("content_type") == "abstract_only"]
    meta = [r for r in results if r.get("content_type") == "metadata_only"]
    chars = [len(str(r.get("content") or "")) for r in results]
    return {
        "selected": selected,
        "full_text_count": len(full),
        "abstract_only_count": len(abstract),
        "metadata_only_count": len(meta),
        "coverage_of_selected": round(len(full) / selected, 4) if selected else 0.0,
        "avg_content_chars": round(sum(chars) / selected) if selected else 0,
        "fulltext_top_n": top_n or settings.FULLTEXT_TOP_N,
    }


def run_disease(info: dict, dimension: str, dry_run: bool = False) -> dict:
    unit = project.build_disease_unit(info, dimension)
    rounds = variant.build_round_queries(info["disease"], dimension)
    if dry_run:
        for item in rounds:
            pass
        return {}

    request = {"url": settings.EUROPE_PMC_URL, "method": "GET", "params": {"search rounds": rounds}}
    try:
        buckets, seen, total_sum, status, meta = [], set(), 0, None, []
        for item in rounds:
            total, items, status, params = fetch_round(item["query"])
            time.sleep(ROUND_DELAY)
            total_sum += total
            meta.append({
                "label": item["label"],
                "query": item["query"],
                "hitCount": total,
                "fetched": len(items),
                "pageSize": params.get("pageSize"),
            })
            bucket = []
            for record in items:
                key = str(
                    record.get("doi") or record.get("pmid") or record.get("id") or ""
                ).lower()
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                bucket.append(record)
            buckets.append(bucket)


        merged, cursor = [], 0
        while len(merged) < settings.TOP_N and any(cursor < len(b) for b in buckets):
            for bucket in buckets:
                if cursor < len(bucket) and len(merged) < settings.TOP_N:
                    merged.append(bucket[cursor])
            cursor += 1


        original_fulltext_top = settings.FULLTEXT_TOP_N
        effective_fulltext_top = max(original_fulltext_top, settings.TOP_N)
        settings.FULLTEXT_TOP_N = effective_fulltext_top
        try:
            results = [
                project.europe_pmc_item(rank, record, unit)
                for rank, record in enumerate(merged, start=1)
            ]
        finally:
            settings.FULLTEXT_TOP_N = original_fulltext_top
        record = project.build_record(
            unit, variant.MODE, request, status, total_sum, results
        )
        record["variant"] = variant.MODE
        record["rounds"] = meta
        record["merged_unique"] = len(seen)
        record["priors"] = priors_of(info["disease"])
        record["fulltext"] = fulltext_summary(results, effective_fulltext_top)
    except Exception as exc:
        record = project.build_record(
            unit, variant.MODE, request, None, 0, [], error=f"unexpected error: {exc}"
        )
    project.save_json(
        project.disease_output_path(variant.MODE, info["disease"], dimension, ROOT), record
    )
    return record


def main() -> int:
    raw = sys.argv[1:]
    dry_run = "--dry-run" in raw
    dims = list(variant.DIMENSIONS)
    if "--dimension" in raw:
        idx = raw.index("--dimension")
        if idx + 1 < len(raw):
            dims = [raw[idx + 1]]
        raw = raw[:idx] + raw[idx + 2:]
    argv = [arg for arg in raw if not arg.startswith("-")]
    diseases = project.read_disease_table(DATA.parent / TABLE)
    if argv:
        diseases = [info for info in diseases if info["disease"] == argv[0]]

    for info in diseases:
        entries, started = [], time.time()
        for dimension in dims:
            mark = time.time()
            if dry_run:
                run_disease(info, dimension, dry_run=True)
                continue
            record = run_disease(info, dimension)
            entries.append({
                "disease": info["disease"],
                "dimension": dimension,
                "source": variant.MODE,
                "ok": record["ok"],
                "status_code": record["status_code"],
                "total_results": record["total_results"],
                "merged_unique": record.get("merged_unique"),
                "returned_results": record["returned_results"],
                "rounds": len(record.get("rounds", [])),
                "full_text_count": (record.get("fulltext") or {}).get("full_text_count"),
                "seconds": round(time.time() - mark, 1),
                "error": record["error"],
            })
            record.get("fulltext") or {}

        if dry_run:
            continue
        log = {
            "variant": variant.MODE,
            "disease": info["disease"],
            "sheet": info.get("sheet", ""),
            "table": TABLE,
            "mode": f"{variant.MODE}-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "dimensions": list(variant.DIMENSIONS),
            "priors": priors_of(info["disease"]),
            "units": entries,
        }
        log_path = DATA / "output" / project.safe_name(info["disease"]) / "run_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        project.save_json(log_path, log)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
