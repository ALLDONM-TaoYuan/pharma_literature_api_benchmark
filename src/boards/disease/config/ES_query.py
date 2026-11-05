"""Query script for the local literature database (Elasticsearch) interface."""

import re

from config import disease_forms, quoted_phrase, settings


RESERVED = re.compile(r'[^0-9A-Za-z]')


KEYWORDS = {

    "Basic Information": [
        ["epidemiology", "pathogenesis", "classification", "diagnosis"],
    ],

    "Clinical Studies": [
        ["clinical trial", "randomized", "efficacy", "treatment guideline"],
    ],

    "Pre-Clinical Studies": [
        ["in vivo", "in vitro", "cell line", "animal model"],
    ],
}


def es_phrase(word: str) -> str:
    text = str(word or "").strip()
    if not text:
        return ""
    if RESERVED.search(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def keyword_groups(dimension: str) -> list:
    groups = []
    for words in KEYWORDS.get(dimension, []):
        groups.append({"raw": " OR ".join(words), "words": list(words)})
    return groups


def first_group(dimension: str, groups: list = None) -> list:
    source = groups if groups is not None else keyword_groups(dimension)
    for group in source or []:
        words = list(group.get("words") or [])
        if words:
            return words
    return []


def anchor_tiers(disease: str) -> list:
    text = str(disease or "").strip()
    if not text:
        return []
    tokens = text.split()
    tiers = [("full name", disease_forms(text))]
    if len(tokens) > 4:
        tiers.append(("first three words", [" ".join(tokens[:3])]))
    if len(tokens) > 3:
        tiers.append(("first two words", [" ".join(tokens[:2])]))
    return tiers


def build_query_text(
    disease: str,
    dimension: str = None,
    groups: list = None,
    forms: list = None,
    words_limit: int = None,
) -> str:
    limit = words_limit or settings.ES_WORDS_LIMIT
    names = list(forms) if forms is not None else disease_forms(disease)
    anchor = " OR ".join(quoted_phrase(name) for name in names if str(name).strip())
    body = " OR ".join(es_phrase(word) for word in first_group(dimension, groups)[:limit])
    query = f"({anchor})"
    return f"{query} AND ({body})" if body else query


def build_payload(
    disease: str,
    dimension: str = None,
    groups: list = None,
    size: int = None,
    words_limit: int = None,
    forms: list = None,
) -> dict:
    return {
        "query": {
            "query_string": {
                "query": build_query_text(
                    disease, dimension, groups, forms=forms, words_limit=words_limit
                ),
                "fields": list(settings.ES_SEARCH_FIELDS),
                "default_operator": "and",
            }
        },
        "_source": list(settings.ES_SOURCE_FIELDS),
        "size": size or settings.TOP_N,
        "track_total_hits": True,
    }
