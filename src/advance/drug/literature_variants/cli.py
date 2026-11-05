"""Shared CLI for the six collectors and their query inspectors."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from config import settings

from . import engine


def console():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def options(module, args):
    priors = engine.load_priors(args.priors) if args.priors else {
        "aliases": module.ALIASES, "info_terms": module.INFO_TERMS}


    if getattr(args, "fulltext_top", None):
        settings.FULLTEXT_TOP_N = args.fulltext_top
    if getattr(args, "fulltext_workers", None):
        settings.FULLTEXT_WORKERS = args.fulltext_workers
    return dict(aliases=priors["aliases"], info_terms=priors["info_terms"],
                limit=args.limit, per_round=args.per_round,
                info_mode=args.info_mode, narrow_in_all_rounds=args.narrow_all,
                keywords=module.KEYWORDS, fulltext=not args.no_fulltext,
                merge_order=args.merge_order)


def common_args(parser, module):
    parser.add_argument("--limit", type=int, default=20, help="Final unique papers per entity/dimension (default 20)")
    parser.add_argument("--per-round", type=int, default=20, help="Native top N per query round (default 20)")
    parser.add_argument("--info-mode", choices=("AND", "OR"), default=module.INFO_MODE)
    parser.add_argument("--narrow-all", action="store_true", default=module.NARROW_IN_ALL_ROUNDS,
                        help="Keep dimension keywords in info rounds too")
    parser.add_argument("--merge-order", choices=("rrf", "round"), default="rrf",
                        help="RRF fusion, or historical ES first-seen round order")
    parser.add_argument("--priors", type=Path, help="Override aliases/info_terms JSON for this run")
    parser.add_argument("--no-fulltext", action="store_true", help="Abstract-only; PMC still uses efetch for abstracts")
    parser.add_argument("--fulltext-top", type=int, default=None,
                        help="How many top-ranked hits may fetch full text (default: settings.FULLTEXT_TOP_N)")
    parser.add_argument("--fulltext-workers", type=int, default=None,
                        help="Parallel full-text fetches (default: settings.FULLTEXT_WORKERS)")
    parser.add_argument("--retries", type=int, default=None, help="Search request attempts")
    parser.add_argument("--timeout", type=float, default=None, help="Search timeout in seconds")


def validate(parser, args):
    if not 1 <= args.limit <= 1000 or not 1 <= args.per_round <= 1000:
        parser.error("--limit and --per-round must be between 1 and 1000")
    if args.retries is not None and args.retries < 1:
        parser.error("--retries must be positive")
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout must be positive")


def make_plan(module, name, dimension, opts):
    return engine.build_rounds(module.BACKEND, module.VARIANT, name, dimension,
                               opts["aliases"], opts["info_terms"], opts["info_mode"],
                               opts["narrow_in_all_rounds"], opts["keywords"])


def query_main(module, argv=None):
    console()
    parser = argparse.ArgumentParser(description=module.MODE + " query inspector")
    parser.add_argument("entity", nargs="?")
    parser.add_argument("dimension", nargs="?", choices=engine.DIMENSIONS, default=engine.DIMENSIONS[0])
    parser.add_argument("--run", action="store_true", help="Execute requests; default only prints queries")
    parser.add_argument("--compare", action="store_true", help="Execute baseline and this variant with identical budgets")
    common_args(parser, module)
    args = parser.parse_args(argv)
    validate(parser, args)
    opts = options(module, args)
    if not args.entity:
        for info in load_infos(None):
            print(info["drug"], opts["aliases"].get(info["drug"], []))
        return 0
    if not args.run and not args.compare:
        print(json.dumps(make_plan(module, args.entity, args.dimension, opts), ensure_ascii=False, indent=2))
        return 0
    info = {"drug": args.entity, "domain": ""}
    unit = engine.project.build_unit(info, args.dimension, args.entity, False)
    client = engine.SearchClient(args.retries, args.timeout)
    record = engine.retrieve(unit, module.BACKEND, module.VARIANT, client=client, **opts)
    report = {"source": module.MODE, "ok": record["ok"], "error": record["error"],
              "candidate_unique_count": record["candidate_unique_count"],
              "returned_results": record["returned_results"],
              "papers": [{k: item.get(k) for k in ("rank", "title", "doi", "url", "content_type")}
                         for item in record["results"]]}
    if args.compare:
        baseline = engine.retrieve(unit, module.BACKEND, 1, client=client, **opts)
        def keys(result):
            return {engine.identity_keys(item)[0] for item in result["results"]}
        a, b = keys(baseline), keys(record)
        report["comparison"] = {"baseline_ok": baseline["ok"], "baseline_error": baseline["error"],
                                "baseline_count": len(a), "variant_count": len(b),
                                "shared": len(a & b), "variant_only": len(b - a),
                                "union": len(a | b)}
        report["baseline_rounds"] = baseline["rounds"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if record["ok"] and (not args.compare or baseline["ok"]) else 1


def load_infos(tables):
    infos, seen = [], set()
    for table in tables or engine.TABLES:
        path = Path(table)
        if not path.is_absolute():
            path = engine.DATA / path
        if not path.exists():
            raise FileNotFoundError("Test workbook not found: " + str(path))
        for item in engine.project.read_drug_table(path):
            if item["drug"] not in seen:
                infos.append({**item, "table": str(path)})
                seen.add(item["drug"])
    return infos


def collect_main(module, argv=None):
    console()
    parser = argparse.ArgumentParser(description=module.MODE + " batch collector (main drugs + competitors)")
    parser.add_argument("entities", nargs="*", help="Exact drug or sheet names; omitted = all workbook drugs")
    parser.add_argument("--table", action="append", help="Workbook path; repeatable")
    parser.add_argument("--dimension", choices=engine.DIMENSIONS, action="append")
    parser.add_argument("--no-competitors", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Write query plan only; no network")
    parser.add_argument("--output-dir", type=Path, help="Alternative output root, e.g. smoke output")
    common_args(parser, module)
    args = parser.parse_args(argv)
    validate(parser, args)
    opts = options(module, args)
    infos = load_infos(args.table)
    if args.entities:
        matched = {name for name in args.entities for info in infos
                   if name in (info["drug"], info["sheet"])}
        if matched != set(args.entities):
            parser.error("Unknown drugs/sheets: " + ", ".join(set(args.entities) - matched))
        infos = [info for info in infos if info["drug"] in args.entities or info["sheet"] in args.entities]
    output = (args.output_dir or engine.DATA / module.MODE / "output").resolve()
    output.mkdir(parents=True, exist_ok=True)
    client = engine.SearchClient(args.retries, args.timeout)
    failures, plans, logs = 0, [], []
    for info in infos:
        started = time.monotonic()
        units = [(info["drug"], False)]
        if not args.no_competitors:
            units.extend((name, True) for name in info["competitors"])
        entries = []
        for name, competitor in units:
            for dimension in args.dimension or info["dimensions"]:
                unit = engine.project.build_unit(info, dimension, name, competitor)
                if args.dry_run:
                    plans.append({"unit": unit, "source": module.MODE,
                                  "rounds": make_plan(module, name, dimension, opts),
                                  "limit": args.limit, "per_round": args.per_round,
                                  "merge_order": args.merge_order})
                    continue
                record = engine.retrieve(unit, module.BACKEND, module.VARIANT, client=client, **opts)
                folder = output / engine.project.safe_name(info["drug"])
                if competitor:
                    folder = folder / "competitors" / engine.project.safe_name(name)
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (engine.project.safe_name(name) + "_" + dimension + ".json")
                engine.project.save_json(path, record)
                failures += int(not record["ok"])
                entries.append({"object": name, "dimension": dimension, "is_competitor": competitor,
                                "ok": record["ok"], "error": record["error"],
                                "returned_results": record["returned_results"],
                                "candidate_unique_count": record["candidate_unique_count"],
                                "rounds": len(record["rounds"]), "path": str(path)})
                ft = record.get("fulltext") or {}
                print(f"{module.MODE} | {name} | {dimension} | candidates={record['candidate_unique_count']} "
                      f"selected={record['returned_results']} | fulltext={ft.get('full_text_count', 0)}"
                      f"/{ft.get('selected', record['returned_results'])}"
                      f"(avg {ft.get('avg_full_text_chars', 0)} chars) | ok={record['ok']}", flush=True)
        if entries:
            log = {"drug": info["drug"], "sheet": info["sheet"], "table": info["table"],
                   "source": module.MODE, "generated_at": datetime.now().isoformat(timespec="seconds"),
                   "seconds": round(time.monotonic() - started, 1), "units": entries}
            folder = output / engine.project.safe_name(info["drug"])
            folder.mkdir(parents=True, exist_ok=True)
            engine.project.save_json(folder / "run_log.json", log)
            logs.append(log)
    if args.dry_run:
        engine.project.save_json(output / "query_plan.json", {"source": module.MODE, "units": plans})
        print(f"Dry run: {len(plans)} units; plan saved to {output / 'query_plan.json'}")
    else:
        engine.project.save_json(output / "batch_log.json", {"source": module.MODE, "failures": failures, "runs": logs})
    return 1 if failures else 0
