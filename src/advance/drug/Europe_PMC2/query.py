"""Europe_PMC2: isolated query configuration and read-only query inspector."""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("drug", "Europe_PMC2")
from literature_variants import engine
from literature_variants.cli import query_main

BACKEND = 'Europe_PMC'
VARIANT = 2
MODE = 'Europe_PMC2'
DIMENSIONS = engine.DIMENSIONS
PRIORS = engine.load_priors()
ALIASES = copy.deepcopy(PRIORS["aliases"])
INFO_TERMS = copy.deepcopy(PRIORS["info_terms"])
KEYWORDS = copy.deepcopy(engine.BASE_MODULES[BACKEND].KEYWORDS)
INFO_MODE = "AND"
NARROW_IN_ALL_ROUNDS = False


def aliases_of(entity):
    return engine.aliases_of(entity, ALIASES)


def info_groups(entity):
    return INFO_TERMS.get(entity, {})


def keyword_groups(dimension):
    return engine.keyword_groups(BACKEND, dimension, KEYWORDS)


def build_query_text(entity, dimension="Basic Information", anchor=None, info_group=None, with_narrow=True):
    return engine.build_query_text(BACKEND, entity, dimension, anchor, info_group,
                                   with_narrow, INFO_MODE, KEYWORDS)


def build_round_queries(entity, dimension="Basic Information"):
    return engine.build_rounds(BACKEND, VARIANT, entity, dimension, ALIASES, INFO_TERMS,
                               INFO_MODE, NARROW_IN_ALL_ROUNDS, KEYWORDS)


def run_rounds(entity, dimension="Basic Information", limit=20, per_round=20, **kwargs):
    unit = engine.project.build_unit({"drug": entity}, dimension, entity, False)
    return engine.retrieve(unit, BACKEND, VARIANT, ALIASES, INFO_TERMS,
                           limit=limit, per_round=per_round, keywords=KEYWORDS,
                           info_mode=INFO_MODE, narrow_in_all_rounds=NARROW_IN_ALL_ROUNDS, **kwargs)


if __name__ == "__main__":
    raise SystemExit(query_main(sys.modules[__name__]))
