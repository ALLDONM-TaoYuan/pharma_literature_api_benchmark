"""Query script for the Europe PMC interface."""

from config import flatten_words, phrase


def build_disease_query(disease: str, groups: list) -> str:
    body = " OR ".join(phrase(word) for word in flatten_words(groups))
    return f"({disease.strip()}) AND ({body})"

