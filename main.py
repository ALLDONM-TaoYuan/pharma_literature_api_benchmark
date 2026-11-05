"""Project controller: pick a run mode -> pick a test object -> pick interfaces -> start collecting.

Usage:
    python main.py                                   interactive, step by step
    python main.py --mode normal --board drug        run every interface of one board directly
    python main.py --mode normal --board drug --sources Europe_PMC,PMC
    python main.py --mode advance --board drug --variant PMC2
    python main.py list                              interface overview and credential status
    python main.py check                             structure check
    python main.py --mode normal --board drug -- --table "approved drugs.xlsx"
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from src import interfaces
from src.console import setup_output
from src.paths import advance_data, advance_src, board_data, board_src

setup_output()

MODES = (
    ("normal", "normal mode", "collect per object, per dimension, per interface"),
    ("advance", "advance mode", "interface variant comparison experiments in the advance area"),
)

BOARDS = (
    ("disease", "disease", "HIV-1 AIDS, ischemic heart disease"),
    ("drug", "drug", "KT-621, BNT327, NTLA-2002"),
    ("target", "target", "BRIP1/DHX9, HIV-1 capsid, JAK1"),
)

HELP = """Project controller: pick a run mode -> pick a test object -> pick interfaces -> start collecting.

Usage:
    python main.py                                   interactive
    python main.py --mode normal --board drug        run every interface of one board
    python main.py --mode normal --board drug --sources Europe_PMC,PMC
    python main.py --mode advance --board drug --variant PMC2
    python main.py list                              interface overview and credential status
    python main.py check                             structure check

Options:
    --mode normal|advance   run mode
    --board disease|drug|target
    --sources comma-separated interface names; run only these
    --variant  variant to run in advance mode
    --dry-run               print the command that would run, without running it
    --                      arguments after this are passed through to the underlying script
"""


def ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer or default


def ask_choice(title: str, options) -> str:
    print()
    print(title)
    for index, (key, label, note) in enumerate(options, 1):
        print("  %d) %-8s %s" % (index, label, note))
    while True:
        raw = ask("  Choose [1-%d]: " % len(options))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print("  Enter a number from the list.")


def ask_list(title: str, names, labels=None) -> list:
    print()
    print(title)
    for name in names:
        note = labels.get(name, "") if labels else ""
        print("  %-16s %s" % (name, note))
    raw = ask("  Which ones? (comma-separated; press Enter for all):")
    if not raw:
        return list(names)
    picked = []
    for item in raw.replace(", ", ",").split(","):
        item = item.strip()
        if item and item not in picked:
            picked.append(item)
    return picked


def run_command(command, cwd: Path, dry: bool = False) -> int:
    print("[run] cd %s && python %s" % (cwd, " ".join(command[1:])), flush=True)
    if dry:
        return 0
    return subprocess.call([sys.executable] + list(command[1:]), cwd=str(cwd))


def cmd_list() -> int:
    status = interfaces.credential_status()
    print("== Interfaces in normal mode ==")
    print("%-18s %-28s %-26s %s" % ("interface", "description", "supported boards", "credentials"))
    for item in interfaces.BASE_INTERFACES:
        missing = interfaces.missing_for(item, status)
        if missing:
            cred = "missing: " + ", ".join(missing)
        elif item.optional:
            cred = "optional: " + ", ".join(item.optional)
        else:
            cred = "none needed"
        print("%-18s %-28s %-26s %s" % (item.name, item.label, ", ".join(item.boards), cred))
    print()
    print("== Interface variants in advance mode (one set per board) ==")
    for name in interfaces.ADVANCE_VARIANTS:
        print("  %-16s %s" % (name, interfaces.VARIANT_LABELS.get(name, "")))
    print()
    print("== Environment variable status ==")
    for key, ok in status.items():
        print("  %-22s %s" % (key, "configured" if ok else "not configured"))
    return 0


def cmd_check() -> int:
    problems = []
    for board, label, _ in BOARDS:
        code_dir = board_src(board)
        if not (code_dir / "main.py").exists():
            problems.append("missing board controller: src/boards/%s/main.py" % board)
        if not (code_dir / "config" / "settings.py").exists():
            problems.append("missing board settings: src/boards/%s/config/settings.py" % board)
        for variant in interfaces.ADVANCE_VARIANTS:
            folder = advance_src(board) / variant
            if not folder.is_dir():
                problems.append("missing variant directory: src/advance/%s/%s" % (board, variant))
            elif not list(folder.glob("run_*.py")):
                problems.append("variant has no collector script: src/advance/%s/%s" % (board, variant))
        for item in interfaces.base_for(board):
            if not (board_data(board) / item.name).is_dir():
                problems.append("missing interface directory: %s/%s" % (board, item.name))
    print("Expected boards: %d, advance variants: %d" % (len(BOARDS), len(interfaces.ADVANCE_VARIANTS)))
    if problems:
        print("Problems found:")
        for item in problems:
            print("  -", item)
        return 1
    print("Structure check passed: %d boards x %d interface variants, none missing." % (
        len(BOARDS), len(interfaces.ADVANCE_VARIANTS)))
    return 0


def cmd_normal(board: str, sources, sheets, extra, dry: bool) -> int:
    code_dir = board_src(board)
    command = [sys.executable, str(code_dir / "main.py")]
    if sources:
        command += ["--sources", ",".join(sources)]
    command += list(sheets or [])
    command += list(extra or [])
    return run_command(command, board_data(board), dry)


def cmd_advance(board: str, variant, sheets, extra, dry: bool) -> int:
    code_dir = advance_src(board)
    if variant in (None, "", "baseline"):
        command = [sys.executable, str(code_dir / "main.py")]
        command += list(sheets or [])
        command += list(extra or [])
        return run_command(command, advance_data(board), dry)
    folder = code_dir / variant
    runners = sorted(folder.glob("run_*.py")) if folder.is_dir() else []
    if not runners:
        print("no such variant: src/advance/%s/%s" % (board, variant))
        return 2
    command = [sys.executable, str(runners[0])]
    command += list(extra or [])
    return run_command(command, advance_data(board), dry)


def interactive(dry: bool) -> int:
    mode = ask_choice("Choose a run mode", MODES)
    board = ask_choice("Choose a test object", BOARDS)
    if mode == "normal":
        status = interfaces.credential_status()
        labels = {}
        for item in interfaces.base_for(board):
            missing = interfaces.missing_for(item, status)
            note = item.label
            if missing:
                note += " (missing credentials:" + ", ".join(missing) + ")"
            labels[item.name] = note
        names = list(labels)
        picked = ask_list("Interfaces available for this board", names, labels)
        unknown = [name for name in picked if name not in names]
        if unknown:
            print("this board has no such interfaces: %s" % ", ".join(unknown))
            return 2
        return cmd_normal(board, picked, [], [], dry)
    picked = ask_list("Which variants to run (advance mode)", list(interfaces.ADVANCE_VARIANTS),
                      interfaces.VARIANT_LABELS)
    unknown = [name for name in picked if name not in interfaces.ADVANCE_VARIANTS]
    if unknown:
        print("no such variants: %s" % ", ".join(unknown))
        return 2
    for variant in picked:
        code = cmd_advance(board, variant, [], [], dry)
        if code != 0:
            return code
    return 0


def parse_options(argv):
    options = {"mode": None, "board": None, "sources": None, "variant": None, "dry": False}
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--mode" and index + 1 < len(argv):
            options["mode"] = argv[index + 1]
            index += 2
        elif item == "--board" and index + 1 < len(argv):
            options["board"] = argv[index + 1]
            index += 2
        elif item == "--sources" and index + 1 < len(argv):
            options["sources"] = [part.strip() for part in argv[index + 1].split(",")
                                  if part.strip()]
            index += 2
        elif item == "--variant" and index + 1 < len(argv):
            options["variant"] = argv[index + 1]
            index += 2
        elif item == "--dry-run":
            options["dry"] = True
            index += 1
        else:
            raise SystemExit("unknown argument: %s (see --help for usage)" % item)
    return options


def main() -> int:
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        cut = argv.index("--")
        extra = argv[cut + 1:]
        argv = argv[:cut]

    if argv and argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if argv and argv[0] == "list":
        return cmd_list()
    if argv and argv[0] == "check":
        return cmd_check()

    options = parse_options(argv)
    dry = options["dry"]
    mode = options["mode"]
    board = options["board"]

    if mode is None or board is None:
        return interactive(dry)
    if mode not in ("normal", "advance"):
        raise SystemExit("--mode must be normal or advance")
    if board not in [name for name, _, _ in BOARDS]:
        raise SystemExit("--board must be disease, drug or target")
    if mode == "normal":
        if options["variant"]:
            raise SystemExit("--variant is only used in advance mode")
        return cmd_normal(board, options["sources"], [], extra, dry)
    return cmd_advance(board, options["variant"], [], extra, dry)


if __name__ == "__main__":
    raise SystemExit(main())
