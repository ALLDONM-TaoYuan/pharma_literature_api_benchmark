"""Query script for the Europe PMC interface (word lists and query strings are managed by this script itself)."""

from config import drug_forms, flatten_words, phrase, quoted_phrase


KEYWORDS = {
    "Basic Information": [
        ["mechanism of action", "inhibitor", "antagonist", "agonist"],
        ["pharmacokinetics", "half-life", "bioavailability"],
        ["dosage form", "formulation", "oral", "intravenous"],
        ["orphan drug", "breakthrough therapy", "fast track", "approval"],
    ],
    "Clinical Studies": [
        ["clinical trial"],
        ["randomized", "placebo-controlled", "open-label"],
        ["efficacy", "response rate", "overall survival", "progression-free survival"],
        ["safety", "adverse events", "tolerability"],
    ],
    "Non-Clinical Studies": [
        ["in vitro", "cell line", "IC50", "assay"],
        ["in vivo", "mouse", "rat", "xenograft"],
        ["pharmacokinetics", "Cmax", "AUC", "clearance"],
        ["toxicity", "hERG", "Ames", "toxicology"],
    ],
}


def keyword_groups(dimension: str) -> list:
    return [
        {"raw": " OR ".join(words), "words": list(words)}
        for words in KEYWORDS.get(dimension, [])
    ]


def build_drug_query(drug: str, dimension: str = None, groups: list = None) -> str:
    groups = groups if groups is not None else keyword_groups(dimension)
    anchor = " OR ".join(quoted_phrase(name) for name in drug_forms(drug))
    body = " OR ".join(phrase(word) for word in flatten_words(groups))
    return f"({anchor}) AND ({body})"


def build_params(query: str, sort: str = None, page_size: int = None) -> dict:
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": page_size,
    }
    if sort:
        params["sort"] = sort
    return params
