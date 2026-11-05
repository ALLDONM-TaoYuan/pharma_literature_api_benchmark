"""ES4 collector: multi-round aliases plus manual info concept groups, written to ES4/output/<object>/<object>_{dimension}.json."""

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
DATA = variant_data("drug", "ES4")


import main as proj_main
from config import settings
import query as variant

TABLES = ('approved drugs.xlsx', 'unapproved drugs.xlsx')


def run_object(info, name, is_competitor, dimension):
    unit = proj_main.build_unit(info, dimension, name, is_competitor)
    local = proj_main.with_keyword_groups(unit, variant.keyword_groups(dimension))
    request = {"url": proj_main.es_endpoint(), "method": "POST(JSON)", "params": {}}
    try:
        rounds, total_sum, hits = variant.run_rounds(name, dimension, size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),
            "narrow_keywords": variant.first_group(dimension),
            "info concept groups": variant.info_groups(name),
            "search rounds": rounds,
            "size": settings.TOP_N,
        }
        results = [proj_main.es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        record = proj_main.build_record(local, "ES4", request, 200, total_sum, results)
        record["es4_rounds"] = rounds
        record["es4_merged_unique"] = len(hits)
        record["es4_info"] = variant.info_groups(name)
    except Exception as exc:
        record = proj_main.build_record(local, "ES4", request, None, 0, [], error=f"unexpected error: {exc}")
    competitor = name if is_competitor else None
    proj_main.save_json(proj_main.interface_output_path('ES4', info['drug'], name, dimension, competitor, ROOT), record)
    return record


def main():
    argv = sys.argv[1:]
    only = argv[0] if argv and not argv[0].startswith("-") else None
    for table in TABLES:
        path = DATA.parent / table
        if not path.exists():
            continue
        infos = proj_main.read_drug_table(path)
        if only:
            infos = [info for info in infos if info['drug'] == only]

        for info in infos:
            entries = []
            started = time.time()
            for dimension in variant.DIMENSIONS:
                mark = time.time()
                for obj, is_comp in [(info['drug'], False)] + [(c, True) for c in info['competitors']]:
                    record = run_object(info, obj, is_comp, dimension)
                    entries.append({
                        "object": obj,
                        "is_competitor": is_comp,
                        "dimension": dimension,
                        "source": "ES4",
                        "ok": record["ok"],
                        "status_code": record["status_code"],
                        "total_results": record["total_results"],
                        "returned_results": record["returned_results"],
                        "rounds": len(record.get("es4_rounds", [])),
                        "merged_unique": record.get("es4_merged_unique"),
                        "seconds": round(time.time() - mark, 1),
                        "error": record["error"],
                    })


            log = {
                "object": info['drug'],
                "sheet": info.get("sheet", ""),
                "table": table,
                "mode": "ES4-info-match",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "seconds": round(time.time() - started, 1),
                "sources": ["ES4"],
                "dimensions": list(variant.DIMENSIONS),
                "info_groups": variant.info_groups(info['drug']),
                "units": entries,
            }
            log_path = DATA / "output" / proj_main.safe_name(info['drug']) / "run_log.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            proj_main.save_json(log_path, log)


if __name__ == "__main__":
    main()
