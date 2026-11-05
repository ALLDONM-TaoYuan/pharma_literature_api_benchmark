"""Europe_PMC: standalone collector for the Europe_PMC baseline interface of the drug board."""
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
DATA = variant_data("drug", "Europe_PMC")


import main as project

TABLE = "approved drugs.xlsx"
SOURCE = "Europe_PMC"
DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Non-Clinical Studies')


def out_path(info: dict, name: str, dimension: str, is_competitor: bool) -> Path:
    base = DATA / "output" / project.safe_name(info["drug"])
    if is_competitor:
        base = base / "competitors" / project.safe_name(name)
    return base / f"{project.safe_name(name)}_{dimension}.json"


def run_one(info: dict, dimension: str, name: str, is_competitor: bool) -> dict:
    unit = project.build_unit(info, dimension, name, is_competitor)
    record = project.FETCHERS[SOURCE](unit)
    project.save_json(out_path(info, name, dimension, is_competitor), record)
    return record


def main() -> int:
    argv = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    infos = project.read_drug_table(DATA.parent / TABLE)
    if argv:
        infos = [info for info in infos if info["drug"] == argv[0]]

    for info in infos:
        for dimension in DIMENSIONS:
            for name, is_competitor in [(info["drug"], False)] + [(c, True) for c in info.get("competitors", [])]:
                run_one(info, dimension, name, is_competitor)


    return 0


if __name__ == "__main__":
    raise SystemExit(main())
