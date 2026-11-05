"""The interface registry and per-interface settings. 

All interfaces are managed here: what they are called, which boards support them, what credentials they need and where their endpoints are. 
Credentials themselves are not stored here; src/credentials.py reads them from the environment. 
"""

from dataclasses import dataclass

from src import credentials

BOARDS = ("disease", "drug", "target")

# ---------- endpoints of the public literature databases ----------

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

PMC_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PMC_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PMC_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

CLINICALTRIALS_URL = "https://clinicaltrials.gov/api/v2/studies"
ARXIV_URL = "https://export.arxiv.org/api/query"
TAVILY_URL = "https://api.tavily.com/search"
OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# ---------- local literature database (Elasticsearch) ----------

ES_URL = credentials.ES_URL
ES_INDEX = credentials.ES_INDEX
ES_USER = credentials.ES_USER
ES_PASSWORD = credentials.ES_PASSWORD
ES_USE_PROXY = False
ES_SEARCH_FIELDS = ("article_title_en", "abstract_en")
ES_SOURCE_FIELDS = (
    "id",
    "article_title_en",
    "abstract_en",
    "publication_year",
    "journal_title",
    "journal_iso_abbr",
    "doi",
    "impact_factor",
    "jcr_quartile",
    "article_type",
)

# ---------- credential forwarding: board code still uses settings.XXX ----------

TAVILY_API_KEY = credentials.TAVILY_API_KEY
OPENFDA_API_KEY = credentials.OPENFDA_API_KEY
PROXY_URL = credentials.PROXY_URL
NCBI_EMAIL = credentials.NCBI_EMAIL


@dataclass(frozen=True)
class Interface:
    name: str
    label: str
    boards: tuple
    needs: tuple = ()
    optional: tuple = ()

    def available_for(self, board: str) -> bool:
        return board in self.boards


BASE_INTERFACES = (
    Interface("Europe_PMC", "European literature database", BOARDS),
    Interface("PMC", "US NCBI literature database", BOARDS),
    Interface("ClinicalTrials", "clinical trial registry", BOARDS),
    Interface("arxiv", "preprint server", BOARDS),
    Interface("openFDA", "FDA drug label database", ("disease", "target"), optional=("OPENFDA_API_KEY",)),
    Interface("tavily", "general web search", BOARDS, needs=("TAVILY_API_KEY",)),
    Interface("tavily_guideline", "targeted guideline search", ("disease",), needs=("TAVILY_API_KEY",)),
    Interface("ES", "local literature database", BOARDS, needs=("ES_URL", "ES_USER", "ES_PASSWORD")),
)

ADVANCE_VARIANTS = (
    "ES1", "ES2", "ES3", "ES4",
    "Europe_PMC", "Europe_PMC2", "Europe_PMC3", "Europe_PMC4",
    "PMC1", "PMC2", "PMC3", "PMC4",
)

VARIANT_LABELS = {
    "ES1": "local database, baseline query",
    "ES2": "local database, one round per alias",
    "ES3": "local database, aliases alone plus info term expansion",
    "ES4": "local database, baseline plus info rounds",
    "Europe_PMC": "European literature database, baseline query",
    "Europe_PMC2": "European literature database, one round per alias",
    "Europe_PMC3": "European literature database, aliases alone plus info term expansion",
    "Europe_PMC4": "European literature database, baseline plus info rounds",
    "PMC1": "NCBI literature database, baseline query",
    "PMC2": "NCBI literature database, one round per alias",
    "PMC3": "NCBI literature database, aliases alone plus info term expansion",
    "PMC4": "NCBI literature database, baseline plus info rounds",
}


def base_for(board: str) -> tuple:
    return tuple(item for item in BASE_INTERFACES if item.available_for(board))


def find(name: str) -> Interface:
    for item in BASE_INTERFACES:
        if item.name == name:
            return item
    raise KeyError(name)


def credential_status() -> dict:
    return {
        "TAVILY_API_KEY": bool(credentials.TAVILY_API_KEY),
        "OPENFDA_API_KEY": bool(credentials.OPENFDA_API_KEY),
        "ES_URL": bool(credentials.ES_URL),
        "ES_INDEX": bool(credentials.ES_INDEX),
        "ES_USER": bool(credentials.ES_USER),
        "ES_PASSWORD": bool(credentials.ES_PASSWORD),
        "PROXY_URL": bool(credentials.PROXY_URL),
    }


def missing_for(item: Interface, status: dict) -> tuple:
    return tuple(name for name in item.needs if not status.get(name))
