"""Query script for the arxiv interface."""

from config import flatten_words, phrase


def arxiv_word(word: str) -> str:
    return f"all:{phrase(word)}"


def build_disease_query(disease: str, groups: list) -> str:
    anchor = " AND ".join(arxiv_word(word) for word in disease.split())
    body = " OR ".join(arxiv_word(word) for word in flatten_words(groups))
    return f"({anchor}) AND ({body})"
