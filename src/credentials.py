"""Credentials are read only from environment variables or .env; no real values are stored in this file. 

Real values go in .env at the repository root (excluded by .gitignore), or straight into environment variables. 
"""

import os
from pathlib import Path


def load_dotenv() -> None:
    """Walk up from this file looking for .env and load it into the environment; existing values are not overwritten."""
    for folder in Path(__file__).resolve().parents:
        env_file = folder / ".env"
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        return


load_dotenv()

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
OPENFDA_API_KEY = os.environ.get("OPENFDA_API_KEY", "")

ES_URL = os.environ.get("ES_URL", "")
ES_INDEX = os.environ.get("ES_INDEX", "")
ES_USER = os.environ.get("ES_USER", "")
ES_PASSWORD = os.environ.get("ES_PASSWORD", "")

PROXY_URL = (
    os.environ.get("HTTPS_PROXY")
    or os.environ.get("HTTP_PROXY")
    or os.environ.get("https_proxy")
    or os.environ.get("http_proxy")
    or ""
)

NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
