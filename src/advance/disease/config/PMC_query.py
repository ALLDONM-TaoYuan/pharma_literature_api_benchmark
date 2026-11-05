"""Query script for the PMC (NCBI E-utilities) interface."""

from config import phrase


PMC_DISEASE_WORDS_LIMIT = 1


def build_disease_query(disease: str, groups: list) -> str:
    anchor = " AND ".join(f"{phrase(word)}[AllFields]" for word in disease.split())
    words = []
    for group in groups:
        words.extend(group["words"][:PMC_DISEASE_WORDS_LIMIT])
    body = " OR ".join(f"{phrase(word)}[AllFields]" for word in dict.fromkeys(words))
    return f"({anchor}) AND ({body})"
