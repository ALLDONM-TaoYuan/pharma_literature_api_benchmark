"""Europe_PMC3 collector: multi-round aliases -> merge and deduplicate the rounds -> fetch full text for the top N -> write JSON."""
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
DATA = variant_data("target", "Europe_PMC3")


import main as project
from config import Europe_PMC_query, settings
import query as variant

TABLE = "target.xlsx"
ROUND_DELAY = 0.6


def fetch_round(query_text: str):
    page = settings.DUAL_SORT_TOP_N
    relevance = Europe_PMC_query.build_params(query_text, page_size=page)
    cited = Europe_PMC_query.build_params(
        query_text, sort=settings.EUROPE_PMC_CITED_SORT, page_size=page
    )
    status, payload = project.call_api(
        settings.EUROPE_PMC_URL, relevance,
        validate=lambda data: "hitCount" in data,
        retry_times=8, retry_wait=15,
    )
    total = project.to_int(payload.get("hitCount"))
    items = [(item, "relevance") for item in payload.get("resultList", {}).get("result", [])]
    notes = []
    try:
        _, cited_payload = project.call_api(
            settings.EUROPE_PMC_URL, cited,
            validate=lambda data: "hitCount" in data,
            retry_times=4, retry_wait=15,
        )
        items.extend(
            (item, "citation count")
            for item in cited_payload.get("resultList", {}).get("result", [])
        )
    except Exception as exc:
        notes.append(f"Citation-count sort retrieval failed: {exc}")
    return total, items, notes, status, relevance


def priors_of(target: str, dimension: str, domain: str) -> dict:
    out = {}
    aliases = getattr(variant, "aliases_of", None)
    if aliases:
        out["aliases"] = aliases(target)
    elif hasattr(variant, "base_forms"):
        out["base_forms"] = variant.base_forms(target)
    info_groups = getattr(variant, "info_groups", None)
    if info_groups:
        out["info_groups"] = info_groups(target)
    domain_terms = getattr(variant, "domain_terms", None)
    if domain_terms:
        out["domain_terms"] = domain_terms(domain, dimension)
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


def run_target(info: dict, dimension: str, dry_run: bool = False) -> dict:
    unit = project.build_target_unit(info, dimension)
    local = project.with_keyword_groups(
        unit, Europe_PMC_query.keyword_groups(dimension)
    )
    rounds = variant.build_round_queries(info["target"], dimension, info.get("domain", ""))
    if dry_run:
        for item in rounds:
            pass
        return {}

    url = settings.EUROPE_PMC_URL
    request = {"url": url, "method": "GET", "params": {"search rounds": rounds}}
    try:
        buckets, seen, total_sum, status, notes = [], set(), 0, None, []
        meta = []
        for item in rounds:
            total, hits, round_notes, status, params = fetch_round(item["query"])
            time.sleep(ROUND_DELAY)
            total_sum += total
            notes += round_notes
            meta.append({
                "label": item["label"],
                "query": item["query"],
                "hitCount": total,
                "fetched": len(hits),
                "pageSize": params.get("pageSize"),
            })
            bucket = []
            for record, branch in hits:
                key = str(
                    record.get("doi") or record.get("pmid") or record.get("id") or ""
                ).lower()
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                bucket.append((record, branch))
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
                project.europe_pmc_item(rank, record, local, branch)
                for rank, (record, branch) in enumerate(merged, start=1)
            ]
        finally:
            settings.FULLTEXT_TOP_N = original_fulltext_top
        record = project.build_record(
            local, variant.MODE, request, status, total_sum, results
        )
        record["variant"] = variant.MODE
        record["rounds"] = meta
        record["merged_unique"] = len(seen)
        record["priors"] = priors_of(info["target"], dimension, info.get("domain", ""))
        record["fulltext"] = fulltext_summary(results, effective_fulltext_top)
        record["sort_branches"] = {
            "relevance": sum(1 for _, branch in merged if branch == "relevance"),
            "citation count": sum(1 for _, branch in merged if branch == "citation count"),
        }
        if notes:
            record["notes"] = notes
    except Exception as exc:
        record = project.build_record(
            local, variant.MODE, request, None, 0, [], error=f"unexpected error: {exc}"
        )
    project.save_json(
        project.target_output_path(variant.MODE, info["target"], dimension, ROOT), record
    )
    return record


def main() -> int:
    argv = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    dry_run = "--dry-run" in sys.argv
    targets = project.read_target_table(DATA.parent / TABLE)
    if argv:
        targets = [info for info in targets if info["target"] == argv[0]]

    for info in targets:
        entries, started = [], time.time()
        for dimension in variant.DIMENSIONS:
            mark = time.time()
            if dry_run:
                run_target(info, dimension, dry_run=True)
                continue
            record = run_target(info, dimension)
            entries.append({
                "target": info["target"],
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
            "target": info["target"],
            "sheet": info.get("sheet", ""),
            "table": TABLE,
            "mode": f"{variant.MODE}-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "dimensions": list(variant.DIMENSIONS),
            "priors": priors_of(info["target"], dimension="", domain=info.get("domain", "")),
            "units": entries,
        }
        log_path = DATA / "output" / project.safe_name(info["target"]) / "run_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        project.save_json(log_path, log)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
