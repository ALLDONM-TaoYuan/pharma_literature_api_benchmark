"""Query script for the tavily interface."""

from config import flatten_words


MAX_QUERY_TERMS = 6


def build_disease_payload(disease: str, groups: list) -> dict:
    parts = [disease.strip()]
    parts.extend(flatten_words(groups)[:MAX_QUERY_TERMS])
    return {
        "query": " ".join(dict.fromkeys(part for part in parts if part)),
        "search_depth": "advanced",
    }
