"""Query script for the local literature database (Elasticsearch) interface (this interface's keyword groups and query strings are maintained here)."""

import re

from config import flatten_words, settings


KEYWORDS = {

    "Basic Information": [["gene", "protein"], ["mechanism", "pathway"]],

    "Clinical Studies": [["clinical trial"]],

    "Pre-Clinical Studies": [["in vivo", "in vitro", "cell line", "mouse model"]],

    "Druggability Feasibility Study": [["inhibitor"]],
}


DOMAIN_DIMENSIONS = ("Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")


DOMAIN_TERMS = {
    "Small Cell Lung Cancer / Colorectal Cancer": ["small cell lung cancer", "colorectal cancer"],
    "HIV Infection": ["HIV infection"],
    "Crohn's Disease": ["Crohn's disease"],
    "Atopic Dermatitis / Rheumatoid Arthritis": ["atopic dermatitis", "rheumatoid arthritis"],
    "Plaque Psoriasis": ["plaque psoriasis"],
}


RESERVED = re.compile(r'[^0-9A-Za-z]')


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


def domain_terms(domain: str, dimension: str = None) -> list:
    if dimension and dimension not in DOMAIN_DIMENSIONS:
        return []
    return list(DOMAIN_TERMS.get(str(domain or "").strip(), []))


def build_query_text(
    terms: list,
    dimension: str = None,
    groups: list = None,
    words_limit: int = None,
    group_operator: str = None,
    domain: str = "",
) -> str:
    groups = groups if groups is not None else keyword_groups(dimension)
    limit = words_limit or settings.ES_WORDS_LIMIT
    operator = (group_operator or settings.ES_GROUP_OPERATOR).upper()
    anchor = f"({ ' OR '.join(es_phrase(term) for term in (terms or [])) })"
    if operator == "OR":
        words = flatten_words(groups) + domain_terms(domain, dimension)
        body = " OR ".join(es_phrase(word) for word in words)
        return f"{anchor} AND ({body})" if body else anchor
    clauses = [
        "(" + " OR ".join(es_phrase(word) for word in group["words"][:limit]) + ")"
        for group in groups
        if group["words"][:limit]
    ]
    domains = domain_terms(domain, dimension)
    if domains:
        clauses.append("(" + " OR ".join(es_phrase(word) for word in domains) + ")")
    return " AND ".join([anchor] + clauses)


def build_payload(
    terms: list,
    dimension: str = None,
    groups: list = None,
    size: int = None,
    domain: str = "",
) -> dict:
    return {
        "query": {
            "query_string": {
                "fields": list(settings.ES_SEARCH_FIELDS),
                "query": build_query_text(terms, dimension, groups, domain=domain),
            }
        },
        "_source": list(settings.ES_SOURCE_FIELDS),
        "size": size or settings.TOP_N,
        "track_total_hits": True,
    }
