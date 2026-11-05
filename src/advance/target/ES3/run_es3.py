"""ES3 collector: info-matching search (original-name form plus manual info concept groups), written to ES3/output/<object>/<object>_{dimension}.json."""

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
DATA = variant_data("target", "ES3")


import main as proj_main
from config import settings
import query as variant

TABLES = ('target.xlsx',)


def run_object(info, name, is_competitor, dimension):
    unit = proj_main.build_target_unit(info, dimension)
    local = proj_main.with_keyword_groups(unit, variant.keyword_groups(dimension))
    request = {"url": proj_main.es_endpoint(), "method": "POST(JSON)", "params": {}}
    try:
        rounds, total_sum, hits = variant.run_rounds(info['target'], dimension, size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),
            "narrow_keywords": variant.first_group(dimension),
            "info concept groups": variant.info_groups(info['target']),
            "search rounds": rounds,
            "size": settings.TOP_N,
        }
        results = [proj_main.es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        record = proj_main.build_record(local, "ES3", request, 200, total_sum, results)
        record["es3_rounds"] = rounds
        record["es3_merged_unique"] = len(hits)
        record["es3_info"] = variant.info_groups(info['target'])
    except Exception as exc:
        record = proj_main.build_record(local, "ES3", request, None, 0, [], error=f"unexpected error: {exc}")
    name if is_competitor else None
    proj_main.save_json(proj_main.target_output_path('ES3', info['target'], dimension, ROOT), record)
    return record


def main():
    argv = sys.argv[1:]
    only = argv[0] if argv and not argv[0].startswith("-") else None
    for table in TABLES:
        path = DATA.parent / table
        if not path.exists():
            continue
        infos = proj_main.read_target_table(path)
        if only:
            infos = [info for info in infos if info['target'] == only]

        for info in infos:
            entries = []
            started = time.time()
            for dimension in variant.DIMENSIONS:
                mark = time.time()
                obj = info['target']
                is_comp = False
                record = run_object(info, obj, is_comp, dimension)
                entries.append({
                    "object": obj,
                    "is_competitor": is_comp,
                    "dimension": dimension,
                    "source": "ES3",
                    "ok": record["ok"],
                    "status_code": record["status_code"],
                    "total_results": record["total_results"],
                    "returned_results": record["returned_results"],
                    "rounds": len(record.get("es3_rounds", [])),
                    "merged_unique": record.get("es3_merged_unique"),
                    "seconds": round(time.time() - mark, 1),
                    "error": record["error"],
                })

            log = {
                "object": info['target'],
                "sheet": info.get("sheet", ""),
                "table": table,
                "mode": "ES3-info-match",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "seconds": round(time.time() - started, 1),
                "sources": ["ES3"],
                "dimensions": list(variant.DIMENSIONS),
                "info_groups": variant.info_groups(info['target']),
                "units": entries,
            }
            log_path = DATA / "output" / proj_main.safe_name(info['target']) / "run_log.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            proj_main.save_json(log_path, log)


if __name__ == "__main__":
    main()
