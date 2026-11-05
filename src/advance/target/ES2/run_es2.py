"""ES2 collector: multi-round alias recall against ES, written to ES2/output/{target}/{target}_{dimension}.json (same layout as the original ES directory)."""

import pathlib
import sys
import time
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("target", "ES2")


import main as target_main
from config import settings
import ES2_query as es2

TABLE = "target.xlsx"


def run_target(info: dict, dimension: str) -> dict:
    unit = target_main.build_target_unit(info, dimension)
    local = target_main.with_keyword_groups(unit, es2.keyword_groups(dimension))
    request = {"url": target_main.es_endpoint(), "method": "POST(JSON)", "params": {}}
    try:
        rounds, round_sum, hits = es2.run_rounds(info["target"], dimension, size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),
            "narrow_keywords": [g["raw"] for g in es2.keyword_groups(dimension)],
            "domain_terms": es2.domain_terms(info.get("domain", ""), dimension),
            "aliases": es2.aliases_of(info["target"]),
            "search rounds": rounds,
            "size": settings.TOP_N,
        }
        results = [target_main.es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        record = target_main.build_record(local, "ES2", request, 200, round_sum, results)
        record["es2_rounds"] = rounds
        record["es2_merged_unique"] = len(hits)
        record["es2_aliases"] = es2.aliases_of(info["target"])
    except Exception as exc:
        record = target_main.build_record(local, "ES2", request, None, 0, [], error=f"unexpected error: {exc}")
    target_main.save_json(
        target_main.target_output_path("ES2", info["target"], dimension, ROOT), record
    )
    return record

def main() -> None:
    argv = sys.argv[1:]
    only = argv[0] if argv and not argv[0].startswith("-") else None
    path = DATA.parent / TABLE
    targets = target_main.read_target_table(path)
    if only:
        targets = [info for info in targets if info["target"] == only]

    for info in targets:
        entries = []
        started = time.time()
        for dimension in es2.DIMENSIONS:
            mark = time.time()
            record = run_target(info, dimension)
            entries.append({
                "target": info["target"],
                "dimension": dimension,
                "source": "ES2",
                "ok": record["ok"],
                "status_code": record["status_code"],
                "total_results": record["total_results"],
                "returned_results": record["returned_results"],
                "rounds": len(record.get("es2_rounds", [])),
                "merged_unique": record.get("es2_merged_unique"),
                "seconds": round(time.time() - mark, 1),
                "error": record["error"],
            })

        log = {
            "target": info["target"],
            "sheet": info["sheet"],
            "table": TABLE,
            "mode": "ES2-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "sources": ["ES2"],
            "dimensions": list(es2.DIMENSIONS),
            "aliases": es2.aliases_of(info["target"]),
            "units": entries,
        }
        target_main.save_json(
            DATA / "output" / target_main.safe_name(info["target"]) / "run_log.json", log
        )


if __name__ == "__main__":
    main()
