"""Validate the md report of a variant: 5 sections, each at most 600 characters, every citation traceable in that variant's json."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import advance_data  # noqa: E402
DATA = advance_data("drug")
DIMS = ("Basic Information", "Clinical Studies", "Non-Clinical Studies")
DEFAULT_DRUGS = ("KT-621", "NTLA-2002", "Sunvozertinib", "baxdrostat", "Inclisiran",
                 "BNT327", "Azenosertib", "Zoldonrasib", "Ceralasertib")
CITE = re.compile(r"[((]([A-Za-z_0-9]+)[, ,]([^))]+)[))]")
LIMIT = 600


def ids_of(folder: pathlib.Path) -> set:
    out = set()
    for path in folder.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rec in payload.get("results", []):
            for key in ("doi", "pmcid"):
                value = str(rec.get(key) or "").strip().lower()
                if value:
                    out.add(value)
    return out


def netlen(text: str) -> int:
    return len(re.sub(r"[\s|*#>`]", "", text))


def check(base: pathlib.Path, drug: str) -> tuple:
    md = base / f"{drug}.md"
    if not md.exists():
        return False, "md missing"
    text = md.read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n(?=[1-5]\.)", text) if re.match(r"^[1-5]\.", b)]
    sizes = [netlen(b) for b in blocks]
    main_ids = ids_of(base / drug)
    comp_ids = set()
    comp = base / drug / "competitors"
    if comp.exists():
        for folder in comp.iterdir():
            if folder.is_dir():
                comp_ids |= ids_of(folder)
    cites = [(v, d.strip()) for v, d in CITE.findall(text)]
    out_of_scope = [(v, d) for v, d in cites if d.lower() not in main_ids | comp_ids]
    strict = " ".join(blocks[1:4]) if len(blocks) >= 4 else ""
    bad234 = [(v, d) for v, d in CITE.findall(strict) if d.strip().lower() not in main_ids]
    over = [n for n in sizes if n > LIMIT]
    signed = "derived from the interface response" in text.strip().splitlines()[-1]
    problems = []
    if len(blocks) != 5:
        problems.append(f"section count {len(blocks)}")
    if over:
        problems.append(f"over limit {over}")
    if out_of_scope:
        problems.append(f"citation out of scope {out_of_scope[:2]}")
    if bad234:
        problems.append(f"sections 2-4 cite competitors {bad234[:2]}")
    if not signed:
        problems.append("signature missing")
    return not problems, " / ".join(problems) or "OK"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    variant = sys.argv[1]
    drugs = sys.argv[2:] or list(DEFAULT_DRUGS)
    base = DATA / variant / "output"
    bad = 0
    for drug in drugs:
        ok, note = check(base, drug)
        bad += 0 if ok else 1


    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
