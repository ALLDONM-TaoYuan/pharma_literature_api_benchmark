"""ES2 collector: multi-round alias search against ES, written to ES2/output/{drug}/... (main drug plus competitors), same layout as the original ES directory."""

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
DATA = variant_data("drug", "ES2")


import main as drug_main
from config import settings
import ES2_query as es2

TABLES = ("unapproved drugs.xlsx", "approved drugs.xlsx")


def run_object(info: dict, name: str, is_competitor: bool, dimension: str) -> dict:
    unit = drug_main.build_unit(info, dimension, name, is_competitor)
    local = drug_main.with_keyword_groups(unit, es2.keyword_groups(dimension))
    request = {"url": drug_main.es_endpoint(), "method": "POST(JSON)", "params": {}}
    try:
        rounds, round_sum, hits = es2.run_rounds(name, dimension, size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),
            "narrow_keywords": es2.first_group(dimension),
            "aliases": es2.aliases_of(name),
            "search rounds": rounds,
            "size": settings.TOP_N,
        }
        results = [drug_main.es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        record = drug_main.build_record(local, "ES2", request, 200, round_sum, results)
        record["es2_rounds"] = rounds
        record["es2_merged_unique"] = len(hits)
        record["es2_aliases"] = es2.aliases_of(name)
    except Exception as exc:
        record = drug_main.build_record(local, "ES2", request, None, 0, [], error=f"unexpected error: {exc}")
    competitor = name if is_competitor else None
    drug_main.save_json(
        drug_main.interface_output_path("ES2", info["drug"], name, dimension, competitor, ROOT),
        record,
    )
    return record

def run_table(table_name: str) -> list:
    path = DATA.parent / table_name
    if not path.exists():
        return []
    drugs = drug_main.read_drug_table(path)
    logs = []
    for info in drugs:
        entries = []
        started = time.time()
        for dimension in info["dimensions"]:
            for name, is_competitor in [(info["drug"], False)] + [(c, True) for c in info["competitors"]]:
                mark = time.time()
                record = run_object(info, name, is_competitor, dimension)
                entries.append({
                    "object": name,
                    "is_competitor": is_competitor,
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
            "drug": info["drug"],
            "sheet": info["sheet"],
            "table": table_name,
            "mode": "ES2-multi-round",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "sources": ["ES2"],
            "dimensions": info["dimensions"],
            "units": entries,
        }
        drug_main.save_json(DATA / "output" / drug_main.safe_name(info["drug"]) / "run_log.json", log)
        logs.append(log)
    return logs


def main() -> None:
    tables = sys.argv[1:] or list(TABLES)

    for table_name in tables:
        run_table(table_name)


if __name__ == "__main__":
    main()
