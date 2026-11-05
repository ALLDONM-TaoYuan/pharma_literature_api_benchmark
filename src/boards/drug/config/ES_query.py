"""Query script for the local literature database (Elasticsearch) interface (word lists and query strings are managed by this script itself)."""

import re

from config import drug_forms, quoted_phrase, settings


RESERVED = re.compile(r'[^0-9A-Za-z]')


KEYWORDS = {

    "Basic Information": [["inhibitor", "degrader", "antibody", "small molecule"]],

    "Clinical Studies": [["clinical trial", "efficacy"]],

    "Non-Clinical Studies": [["in vivo", "in vitro", "cell line", "mouse model"]],
}


def keyword_groups(dimension: str) -> list:
    return [
        {"raw": " OR ".join(words), "words": list(words)}
        for words in KEYWORDS.get(dimension, [])
    ]


def es_phrase(word: str) -> str:
    text = str(word or "").strip()
    if not text:
        return ""
    if RESERVED.search(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def first_group(dimension: str, groups: list = None) -> list:
    source = groups if groups is not None else keyword_groups(dimension)
    for group in source or []:
        words = list(group.get("words") or [])
        if words:
            return words
    return []


def build_query_text(
    drug: str,
    dimension: str = None,
    groups: list = None,
    forms: list = None,
    words_limit: int = None,
) -> str:
    limit = words_limit or settings.ES_WORDS_LIMIT
    names = list(forms) if forms is not None else drug_forms(drug)
    anchor = " OR ".join(quoted_phrase(name) for name in names if str(name).strip())
    body = " OR ".join(es_phrase(word) for word in first_group(dimension, groups)[:limit])
    if anchor and body:
        return f"({anchor}) AND ({body})"
    return f"({anchor})" if anchor else f"({body})"


def build_payload(
    drug: str,
    dimension: str = None,
    groups: list = None,
    forms: list = None,
    size: int = None,
) -> dict:
    return {
        "query": {
            "query_string": {
                "fields": list(settings.ES_SEARCH_FIELDS),
                "query": build_query_text(drug, dimension, groups, forms),
            }
        },
        "_source": list(settings.ES_SOURCE_FIELDS),
        "size": size or settings.TOP_N,
        "track_total_hits": True,
    }
