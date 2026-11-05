"""ES1: standalone collector for the ES baseline interface of the target board."""
import sys

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("target", "ES1")


import main as project

TABLE = "target.xlsx"
SOURCE = "ES"
DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies', 'Druggability Feasibility Study')


def out_path(info: dict, dimension: str) -> Path:
    obj = project.safe_name(info["target"])
    return DATA / "output" / obj / f"{obj}_{dimension}.json"


def run_one(info: dict, dimension: str) -> dict:
    unit = project.build_target_unit(info, dimension)
    record = project.FETCHERS[SOURCE](unit)
    project.save_json(out_path(info, dimension), record)
    return record


def main() -> int:
    argv = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    infos = project.read_target_table(DATA.parent / TABLE)
    if argv:
        infos = [info for info in infos if info["target"] == argv[0]]

    for info in infos:
        for dimension in DIMENSIONS:
            run_one(info, dimension)


    return 0


if __name__ == "__main__":
    raise SystemExit(main())
