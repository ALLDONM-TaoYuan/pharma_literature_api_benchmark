"""Query script for the ClinicalTrials.gov interface (word lists and query strings are managed by this script itself)."""

from config import drug_forms, quoted_phrase


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


def keyword_groups(dimension: str) -> list:
    return [
        {"raw": " OR ".join(words), "words": list(words)}
        for words in KEYWORDS.get(dimension, [])
    ]


def build_params(drug: str, dimension: str = None, groups: list = None) -> dict:
    anchor = " OR ".join(quoted_phrase(name) for name in drug_forms(drug))
    return {
        "query.intr": f"({anchor})",
        "pageSize": None,
        "countTotal": "true",
    }
