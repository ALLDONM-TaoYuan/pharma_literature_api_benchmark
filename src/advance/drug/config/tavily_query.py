"""Query script for the tavily interface (word lists and query strings are managed by this script itself)."""

from config import drug_forms, flatten_words


KEYWORDS = {
    "Basic Information": [
        ["mechanism of action", "inhibitor", "antagonist", "agonist"],
        ["pharmacokinetics", "half-life", "bioavailability"],
        ["dosage form", "formulation", "oral", "intravenous"],
        ["orphan drug", "breakthrough therapy", "fast track", "approval"],
    ],
    "Clinical Studies": [
        ["clinical trial", "phase 1", "phase 2", "phase 3"],
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


MAX_QUERY_TERMS = 6


def keyword_groups(dimension: str) -> list:
    return [
        {"raw": " OR ".join(words), "words": list(words)}
        for words in KEYWORDS.get(dimension, [])
    ]


def build_query_text(
    drug: str, dimension: str = None, groups: list = None, domain: str = ""
) -> str:
    groups = groups if groups is not None else keyword_groups(dimension)
    parts = drug_forms(drug)[:1]
    if str(domain or "").strip():
        parts.append(str(domain).strip())
    parts.extend(flatten_words(groups)[:MAX_QUERY_TERMS])
    return " ".join(dict.fromkeys(part for part in parts if part))


def build_payload(
    drug: str, dimension: str = None, groups: list = None, domain: str = ""
) -> dict:
    return {
        "query": build_query_text(drug, dimension, groups, domain),
        "search_depth": "advanced",
    }
