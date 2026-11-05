"""Settings for the disease board: board-specific parameters only. 

Shared settings live in src/settings.py, interface settings in src/interfaces.py, credentials in src/credentials.py. 
"""

import sys
from pathlib import Path


def _add_repo_root() -> None:
    """Add the repository root to sys.path so that src can be imported."""
    for folder in Path(__file__).resolve().parents:
        if (folder / "src" / "__init__.py").exists():
            if str(folder) not in sys.path:
                sys.path.insert(0, str(folder))
            return


_add_repo_root()

from src import interfaces as _interfaces  # noqa: E402
from src import settings as _shared  # noqa: E402

# Forward the shared and interface settings in; board code keeps using settings.XXX
globals().update({k: v for k, v in vars(_shared).items() if k.isupper()})
globals().update({k: v for k, v in vars(_interfaces).items() if k.isupper()})

# ---------------- board-specific ----------------

API_TEST_DIR = ""
DISEASE_TABLE = "disease.xlsx"

USER_AGENT = "pharma-literature-api-benchmark/1.0 (disease retrieval test)"

ES_WORDS_LIMIT = 4
ES_SOURCE_FIELDS = (
    "id",
    "doi",
    "article_title_en",
    "abstract_en",
    "journal_title",
    "journal_iso_abbr",
    "publication_year",
    "publication_time",
    "impact_factor",
    "jcr_quartile",
    "article_type",
    "keywords_en",
)

TAVILY_GUIDELINE_MAX_RESULTS = 10
TAVILY_GUIDELINE_TARGETED = True
