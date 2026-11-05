"""Bounded real-network smoke test of all six variants (not the full experiment)."""
import argparse
import importlib.util
import os

from datetime import datetime

from . import engine
from .cli import console


def main():
    console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default="KT-621")
    parser.add_argument("--dimension", choices=engine.DIMENSIONS, default="Clinical Studies")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--per-round", type=int, default=3)
    parser.add_argument("--no-fulltext", action="store_true")
    args = parser.parse_args()

    engine.settings.RETRY_TIMES = 1
    engine.settings.REQUEST_TIMEOUT = 25
    engine.settings.FULLTEXT_TIMEOUT = 25
    engine.settings.FULLTEXT_RETRY_TIMES = 1
    engine.settings.PMC_BATCH_TIMEOUT = 40
    client = engine.SearchClient(retry_times=1, timeout=25)
    rows = []
    for backend in ("Europe_PMC", "PMC"):
        for variant in (2, 3, 4):
            mode = backend + str(variant)
            spec = importlib.util.spec_from_file_location(mode + "_smoke", engine.ROOT / mode / "query.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            unit = engine.project.build_unit({"drug": args.entity}, args.dimension, args.entity, False)

            record = engine.retrieve(unit, backend, variant, module.ALIASES, module.INFO_TERMS,
                                     limit=args.limit, per_round=args.per_round, keywords=module.KEYWORDS,
                                     client=client, fulltext=not args.no_fulltext)
            folder = engine.DATA / mode / "tests/live"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (engine.project.safe_name(args.entity) + "_" + args.dimension + ".json")
            engine.project.save_json(path, record)
            row = {"mode": mode, "entity": args.entity, "ok": record["ok"], "error": record["error"],
                   "rounds": len(record["rounds"]), "candidate_unique_count": record["candidate_unique_count"],
                   "returned_results": record["returned_results"], "metrics": record["metrics"],
                   "path": os.path.relpath(path, engine.ROOT.parents[2]).replace(os.sep, "/")}
            rows.append(row)

    engine.project.save_json(engine.ROOT / "literature_variants/live_validation.json",
                             {"checked_at": datetime.now().isoformat(timespec="seconds"),
                              "budget": {"per_round": args.per_round, "limit": args.limit}, "runs": rows})
    return int(any(not row["ok"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
