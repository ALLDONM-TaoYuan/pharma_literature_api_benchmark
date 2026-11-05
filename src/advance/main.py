"""advance controller: list / run / check the 12 interface modules of each board."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import advance_data  # noqa: E402
DATA_ROOT = advance_data("")
sys.path.insert(0, str(HERE.parent))

from src.console import setup_output

setup_output()

HELP = """advance controller: list / run / check the 12 interface modules of each board.

Usage:
    python src/advance/main.py list                      # module overview
    python src/advance/main.py run drug ES2              # run one interface of one board
    python src/advance/main.py run drug ES2 --limit 5    # extra arguments are passed to the module script
    python src/advance/main.py check                     # structure check (complete, no duplicates)
    python src/advance/main.py digest drug ES2           # compress the results into evidence digests
    python src/advance/main.py verify-md drug ES2        # validate the md distillation files
"""

PROJECTS = ("drug", "target", "disease")
MODULES = ("ES1", "ES2", "ES3", "ES4",
           "Europe_PMC", "Europe_PMC2", "Europe_PMC3", "Europe_PMC4",
           "PMC1", "PMC2", "PMC3", "PMC4")

DIGEST_DIR = "_digest"

DATA_HINT = re.compile(
    r"(\d+(\.\d+)?\s*(mg|kg|ml|mL|μg|ug|nm|nM|%|months?|weeks?|days?|years?|hours?|h\b))"
    r"|(p\s*[<=>]\s*0?\.\d+)|(\bn\s*=\s*\d+)"
    r"|(IC50|EC50|IC90|AUC|Cmax|T1/2|Tmax|Vss|ORR|OS\b|PFS\b|DOR\b|HR\s*=)"
    r"|(\d+\.\d+\s*(mg|mL)/kg)"
    r"|(\b\d{2,}\s*(patients|participants|subjects))",
    re.IGNORECASE,
)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

NOISE = re.compile(
    r"RRID|CVCL_|\bFBS\b|DMEM|RPMI|GlutaMAX|penicillin|streptomycin|Sigma|Gibco|ATCC|"
    r"cat\.\s*#|cells were (maintained|cultured|purchased|seeded|lysed)|"
    r"Western blot|immunoblot|Fig\.|Figure \d|Supplementary|supplemental|"
    r"×\s*g\b|GraphPad|Mycoplasma|antibod(y|ies) (against|were)|"
    r"bioluminescence imaging|microscope|stained with|paraformaldehyde",
    re.IGNORECASE,
)

STRONG = re.compile(
    r"objective response|overall response|ORR|disease control|complete response|partial response|"
    r"progression-free survival|overall survival|median (OS|PFS|DOR)|hazard ratio|HR\s*=|"
    r"dose-limiting|DLT|maximum tolerated|MTD|recommended (phase 2 )?dose|RP2D|"
    r"adverse event|grade\s*[3-4]|grade ≥\s*3|treatment-related|discontinu|"
    r"IC50|EC50|AUC|Cmax|bioavailability|half-life|T1/2|clearance|"
    r"tumor (volume|growth) (inhibition|reduction)|TGI|regression|"
    r"phase\s*(I|II|III|1|2|3)|randomi[sz]ed|placebo|enrolled|"
    r"conclusion|we conclude|these (data|results) (suggest|show|demonstrate)|"
    r"significant(ly)? (improved|prolonged|reduced|increased)",
    re.IGNORECASE,
)

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s)), ; , ]+")
SEC_RE = re.compile(r"^\d+[., ]", re.M)


def module_dir(project: str, module: str) -> Path:
    """Code directory of a variant."""
    return HERE / project / module


def data_dir(project: str, module: str) -> Path:
    """Result directory of a variant."""
    return DATA_ROOT / project / module


def runner_of(folder: Path):
    found = sorted(folder.glob("run_*.py"))
    return found[0] if found else None


def stats(folder: Path) -> tuple:
    files = [p for p in folder.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def cmd_list() -> int:
    print(f"{'board':<8}{'interface':<13}{'script':<26}{'json':>9}{'fulltext':>9}{'MB':>9}  status")
    for project in PROJECTS:
        for module in MODULES:
            folder = module_dir(project, module)
            data = data_dir(project, module)
            if not folder.exists():
                print(f"{project:<8}{module:<13}{'--':<26}{0:>9}{0:>9}{0:>9}  ✗ directory missing")
                continue
            runner = runner_of(folder)
            out_dir = data / "output"
            jsons = list(out_dir.rglob("*.json")) if out_dir.exists() else []
            full = 0
            for path in jsons:
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                full += text.count('"content_type": "full_text"')
            count, size = stats(data)
            if (folder / "MISSING.md").exists():
                state = ".  source project not created (placeholder)"
            elif jsons:
                state = "✓ has results"
            elif runner:
                state = ".  script only, not run"
            else:
                state = ".  results directory only"
            print(f"{project:<8}{module:<13}{(runner.name if runner else '--'):<26}"
                  f"{len(jsons):>9}{full:>9}{size/1048576:>9.1f}  {state}")
    return 0


def cmd_run(project: str, module: str, extra: list) -> int:
    folder = module_dir(project, module)
    if not folder.exists():
        print(f"no such module: {project}/{module}")
        return 2
    runner = runner_of(folder)
    if runner is None:
        print(f"{project}/{module} has no run_*.py, only collected results. ")
        print(f"to re-run this baseline interface use the board controller: cd src/advance/{project} && python main.py")
        return 2
    command = [sys.executable, str(runner)] + extra
    print(f"[run] cd {project} && python {module}/{runner.name} {' '.join(extra)}".rstrip())
    return subprocess.call(command, cwd=str(DATA_ROOT / project))


def digest_abstract(text: str, limit: int) -> str:
    body = text
    for marker in ("\n# ", "\n## ", "\nAbstract\n", "\nABSTRACT\n"):
        idx = body.find(marker)
        if 200 < idx < 6000:
            body = body[:idx]
            break
    body = re.sub(r"\s+", " ", body).strip()
    return body[:limit]


def digest_sentences(text: str, subject: str, limit: int, budget: int) -> str:
    clean = re.sub(r"\s+", " ", text)
    for marker in (" References ", " REFERENCES ", " Bibliography "):
        idx = clean.rfind(marker)
        if idx > len(clean) * 0.5:
            clean = clean[:idx]
    sents = [s.strip() for s in SENT_SPLIT.split(clean)]
    scored = []
    subj = (subject or "").lower()
    for pos, sent in enumerate(sents):
        if not (45 <= len(sent) <= 400):
            continue
        if NOISE.search(sent):
            continue
        score = 0.0
        if DATA_HINT.search(sent):
            score += 1.0
        if STRONG.search(sent):
            score += 1.6
        if subj and subj in sent.lower():
            score += 1.2
        if score < 1.0:
            continue
        scored.append((score, pos, sent))
    scored.sort(key=lambda x: (-x[0], x[1]))
    keep = sorted(scored[:limit], key=lambda x: x[1])
    out, total = [], 0
    for _, _, sent in keep:
        if total + len(sent) > budget:
            continue
        out.append(sent)
        total += len(sent)
    return " ".join(out)


def digest_item(item: dict, excerpt: int, sent_limit: int, sent_budget: int,
                subject: str = "") -> str:
    title = (item.get("title") or "").strip()
    doi = item.get("doi") or "no DOI"
    url = item.get("url") or ""
    ctype = item.get("content_type") or ""
    content = item.get("content") or ""
    head = f"[r{item.get('rank')}] {title}\nDOI:{doi} | {ctype} | {url}"
    if not content:
        return head + "\n(body missing)\n"
    if ctype == "full_text" and len(content) > excerpt * 1.5:
        ab = digest_abstract(content, excerpt)
        ds = digest_sentences(content, subject, sent_limit, sent_budget)
        body = ab if not ds else f"{ab}\n- key data sentences: {ds}"
    else:
        body = re.sub(r"\s+", " ", content).strip()[: excerpt + 200]
    return f"{head}\n{body}\n"


def digest_index(results: list) -> str:
    lines = ["\n---- remaining hits (metadata only, usable as extra citations)----"]
    for it in results:
        lines.append(f"[r{it.get('rank')}] {it.get('title')} | "
                     f"DOI:{it.get('doi') or 'no DOI'}")
    return "\n".join(lines) + "\n"


def digest_object(obj_dir: Path, dest: Path, top: int, excerpt: int,
                  sent_limit: int, sent_budget: int, competitors: bool) -> list:
    dest.mkdir(parents=True, exist_ok=True)
    made = []

    def one(json_path: Path, label: str, top_n: int, exc: int, sl: int, sb: int,
            subject: str):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return
        results = data.get("results") or []
        head = (
            f"# {label}\n"
            f"interface: {data.get('source')} | object: {data.get('object')} | "
            f"dimension: {data.get('dimension')}\n"
            f"domain: {data.get('domain')} | search keywords: {data.get('keywords')}\n"
            f"total hits: {data.get('total_results')} | returned: {data.get('returned_results')}\n"
        )
        if not data.get("ok"):
            head += f"!! interface error: {data.get('error')}\n"
        chunks = [head]
        for it in results[:top_n]:
            chunks.append(digest_item(it, exc, sl, sb, subject))
        if len(results) > top_n:
            chunks.append(digest_index(results[top_n:]))
        text = "\n".join(chunks)
        target = dest / f"_{label}.txt"
        target.write_text(text, encoding="utf-8")
        made.append((target, len(text)))

    for json_path in sorted(obj_dir.glob("*.json")):
        if json_path.stem.startswith("run_log"):
            continue
        label = json_path.stem.replace(obj_dir.name + "_", "")
        one(json_path, label, top, excerpt, sent_limit, sent_budget, obj_dir.name)

    comp_dir = obj_dir / "competitors"
    if competitors and comp_dir.is_dir():
        for comp in sorted(p for p in comp_dir.iterdir() if p.is_dir()):
            for json_path in sorted(comp.glob("*.json")):
                if json_path.stem.startswith("run_log"):
                    continue
                label = f"Competitor_{comp.name}_{json_path.stem.replace(comp.name + '_', '')}"
                one(json_path, label, 4, 380, 2, 300, comp.name)
    return made


def cmd_digest(argv: list) -> int:
    parser = argparse.ArgumentParser(description="compress variant results into evidence digests")
    parser.add_argument("block", choices=list(PROJECTS))
    parser.add_argument("module")
    parser.add_argument("--obj", default=None)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--excerpt", type=int, default=750)
    parser.add_argument("--sent-limit", type=int, default=3)
    parser.add_argument("--sent-budget", type=int, default=450)
    parser.add_argument("--competitors", type=int, default=1)
    args = parser.parse_args(argv)

    src = data_dir(args.block, args.module) / "output"
    if not src.is_dir():
        print("no results directory: %s" % src)
        return 1
    objs = [p for p in sorted(src.iterdir()) if p.is_dir()]
    if args.obj:
        objs = [p for p in objs if p.name == args.obj]
        if not objs:
            return 1
    out_root = DATA_ROOT / DIGEST_DIR
    for obj_dir in objs:
        dest = out_root / args.block / args.module / obj_dir.name
        made = digest_object(obj_dir, dest, args.top, args.excerpt,
                             args.sent_limit, args.sent_budget, bool(args.competitors))
        print("%s -> %d files" % (obj_dir.name, len(made)))
    return 0


def verify_sections(text: str) -> dict:
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        if SEC_RE.match(line.strip()) and len(line.strip()) < 40:
            if cur:
                out[cur] = len("".join(buf).strip())
            cur, buf = line.strip(), []
        elif cur is not None:
            buf.append(line)
    if cur:
        out[cur] = len("".join(buf).strip())
    return out


def verify_md_file(md: Path, digest_dir: Path) -> list:
    problems = []
    text = md.read_text(encoding="utf-8")
    if not digest_dir.is_dir():
        return ["missing digest directory %s" % digest_dir]
    corpus = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                       for f in digest_dir.glob("*.txt"))
    doilow = corpus.lower()
    for doi in sorted(set(DOI_RE.findall(text))):
        if doi.lower() not in doilow:
            problems.append("DOI not found in the digest: %s" % doi)

    sizes = verify_sections(text)
    if not sizes:
        problems.append("no sections detected")
    for sec, n in sizes.items():
        if n > 600:
            problems.append("%s over 600 characters (%s)" % (sec, n))
        elif n < 200:
            problems.append("%s too short (%s)" % (sec, n))

    first = text.strip().splitlines()[0].strip()
    if first.startswith("#") or SEC_RE.match(first):
        problems.append("first line should be the object name, got: %s" % first[:30])
    if "DeepSeek V4.1 Flash" not in text:
        problems.append("missing the model note line")
    if text.count("DeepSeek V4.1 Flash") > 1:
        problems.append("duplicate model note line")
    if "##" in text:
        problems.append("contains a markdown level-2 heading")
    return problems


def cmd_verify_md(argv: list) -> int:
    parser = argparse.ArgumentParser(description="validate md distillation files")
    parser.add_argument("block", choices=list(PROJECTS), nargs="?")
    parser.add_argument("module", nargs="?")
    args = parser.parse_args(argv)

    blocks = [args.block] if args.block else list(PROJECTS)
    total, bad = 0, 0
    for b in blocks:
        modules = [args.module] if args.module else ["PMC1", "PMC2", "PMC3", "PMC4"]
        for p in modules:
            out = data_dir(b, p) / "output"
            if not out.is_dir():
                continue
            for obj in sorted(x for x in out.iterdir() if x.is_dir()):
                for md in obj.glob("*.md"):
                    total += 1
                    probs = verify_md_file(md, DATA_ROOT / DIGEST_DIR / b / p / obj.name)
                    if probs:
                        bad += 1
                        for x in probs:
                            print("%s: %s" % (md, x))
    print("checked %d md files, %d with problems" % (total, bad))
    return 1 if bad else 0


def cmd_check() -> int:
    problems, seen = [], set()
    for project in PROJECTS:
        for module in MODULES:
            key = f"{project}/{module}"
            if key in seen:
                problems.append(f"duplicate module: {key}")
            seen.add(key)
            folder = module_dir(project, module)
            if not folder.exists():
                problems.append(f"missing directory: {key}")
                continue
            out_dir = data_dir(project, module) / "output"
            has_result = out_dir.exists() and any(out_dir.rglob("*.json"))
            has_runner = runner_of(folder) is not None
            has_missing = (folder / "MISSING.md").exists()
            if not (has_result or has_runner or has_missing):
                problems.append(f"empty shell directory: {key}")
        if not (HERE / project / "main.py").exists():
            problems.append(f"missing board controller:{project}/main.py")
    print(f"expected modules: {len(PROJECTS) * len(MODULES)}, found: {len(seen)}, "
          f"duplicates: {len(seen) - len(set(seen))}")
    if problems:
        print("Problems found:")
        for item in problems:
            print("  -", item)
        return 1
    print(f"Structure check passed: {len(PROJECTS)} boards x {len(MODULES)} interfaces, none missing, no duplicates. ")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    action = argv[0]
    if action == "list":
        return cmd_list()
    if action == "check":
        return cmd_check()
    if action == "run":
        if len(argv) < 3:
            print("Usage: python src/advance/main.py run <board> <module> [module script args]")
            return 2
        return cmd_run(argv[1], argv[2], argv[3:])
    if action == "digest":
        if len(argv) < 3:
            print("Usage: python src/advance/main.py digest <board> <module>")
            return 2
        return cmd_digest(argv[1:])
    if action == "verify-md":
        return cmd_verify_md(argv[1:])
    print(f"unknown command: {action}")
    print(HELP)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
