"""Settings for the drug board: board-specific parameters only. 

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

DRUG_TABLE = "unapproved drugs.xlsx"
DRUG_TABLES = ("approved drugs.xlsx", "unapproved drugs.xlsx")

DRUG_NAME_CELL = (2, 1)
COMPETITOR_COLUMN = 2
COMPETITOR_START_ROW = 2
DOMAIN_COLUMN = 3
SECTION_COLUMN = 4
SECTION_START_ROW = 2
INTERFACE_COLUMNS = {
    "tavily": "E",
    "Europe_PMC": "F",
    "PMC": "G",
    "ClinicalTrials": "H",
    "openFDA": "I",
    "arxiv": "J",
    "ALL": "K",
    "ES": "L",
}

USER_AGENT = "pharma-literature-api-benchmark/1.0 (drug retrieval test)"

ES_WORDS_LIMIT = 6

EUROPE_PMC_SORT = "CITED desc"
EUROPE_PMC_RETRY_TIMES = 5
EUROPE_PMC_RETRY_WAIT = 30

FULLTEXT_PAUSE_SECONDS = 1
FULLTEXT_RETRY_TIMES = 3
FULLTEXT_RETRY_WAIT = 10
FULLTEXT_WORKERS = 4

PMC_WORDS_LIMIT = 2
