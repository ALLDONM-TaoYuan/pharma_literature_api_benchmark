"""ES2 collector: multi-round alias recall against ES, written to ES2/output/{disease}/{disease}_{dimension}.json (same layout as the original ES directory)."""

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
DATA = variant_data("disease", "ES2")


import main as disease_main
from config import settings
import ES2_query as es2

TABLE = "disease.xlsx"


def run_disease(info: dict, dimension: str) -> dict:
    unit = disease_main.build_disease_unit(info, dimension)
    local = disease_main.with_keyword_groups(unit, es2.keyword_groups(dimension))
    request = {"url": disease_main.es_endpoint(), "method": "POST(JSON)", "params": {}}
    try:
        rounds, round_sum, hits = es2.run_rounds(info["disease"], dimension, size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),
            "narrow_keywords": es2.first_group(dimension),
            "aliases": es2.aliases_of(info["disease"]),
            "search rounds": rounds,
            "size": settings.TOP_N,
        }
        results = [disease_main.es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        record = disease_main.build_record(local, "ES2", request, 200, round_sum, results)
        record["es2_rounds"] = rounds
        record["es2_merged_unique"] = len(hits)
        record["es2_aliases"] = es2.aliases_of(info["disease"])
    except Exception as exc:
        record = disease_main.build_record(local, "ES2", request, None, 0, [], error=f"unexpected error: {exc}")
    disease_main.save_json(
        disease_main.disease_output_path("ES2", info["disease"], dimension, ROOT), record
    )
    return record

def main() -> None:
    argv = sys.argv[1:]
    only = argv[0] if argv and not argv[0].startswith("-") else None
    path = DATA.parent / TABLE
    diseases = disease_main.read_disease_table(path)
    if only:
        diseases = [info for info in diseases if info["disease"] == only]

    for info in diseases:
        entries = []
        started = time.time()
        for dimension in es2.DIMENSIONS:
            mark = time.time()
            record = run_disease(info, dimension)
            entries.append({
                "disease": info["disease"],
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
            "disease": info["disease"],
            "sheet": info["sheet"],
            "table": TABLE,
            "mode": "ES2-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "sources": ["ES2"],
            "dimensions": list(es2.DIMENSIONS),
            "aliases": es2.aliases_of(info["disease"]),
            "units": entries,
        }
        disease_main.save_json(
            DATA / "output" / disease_main.safe_name(info["disease"]) / "run_log.json", log
        )


if __name__ == "__main__":
    main()
