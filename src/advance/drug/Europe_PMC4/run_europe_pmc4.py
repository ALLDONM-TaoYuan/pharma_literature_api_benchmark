"""Collect Europe_PMC4 for all workbook drugs and competitors; --dry-run prints no requests."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("drug", "Europe_PMC4")
from literature_variants.cli import collect_main


def main(argv=None):
    spec = importlib.util.spec_from_file_location("Europe_PMC4_query", HERE / "query.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return collect_main(module, argv)


if __name__ == "__main__":
    raise SystemExit(main())
