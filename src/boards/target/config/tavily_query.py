"""Query script for the tavily interface (this interface's keyword groups and request body are maintained here)."""

from config import flatten_words


MAX_QUERY_TERMS = 6


KEYWORDS = {
    "Basic Information": [
        ["gene", "protein", "encoding", "homolog"],
        ["biological function", "catalytic activity", "enzymatic activity"],
        ["tissue distribution", "expression profile", "immunohistochemistry"],
        ["signaling pathway", "downstream", "phosphorylation"],
        ["crystal structure", "domain", "binding site"],
    ],
    "Clinical Studies": [
        ["clinical trial", "randomized", "phase 2", "phase 3"],
        ["inhibitor", "antibody", "targeted therapy"],
        ["efficacy", "response rate", "overall survival", "progression-free survival"],
        ["safety", "adverse events", "tolerability"],
        ["biomarker", "patient selection", "mutation"],
    ],
    "Pre-Clinical Studies": [
        ["in vivo", "mouse model", "xenograft", "knockout"],
        ["in vitro", "cell line", "assay", "organoid"],
        ["pharmacokinetics", "potency", "selectivity", "pharmacodynamics"],
        ["mechanism", "signaling", "pathway", "resistance"],
    ],
    "Druggability Feasibility Study": [
        ["druggability", "binding pocket", "crystal structure", "co-crystal"],
        ["small molecule", "antibody", "peptide", "degrader"],
        ["selectivity", "ADME", "pharmacokinetics", "DMPK"],
        ["drug discovery", "optimization", "clinical failure", "development"],
        ["PDB", "homology model", "molecular docking", "structure-activity"],
    ],
}


def keyword_groups(dimension: str) -> list:
    return [
        {"raw": " OR ".join(words), "words": list(words)}
        for words in KEYWORDS.get(dimension, [])
    ]


def build_target_payload(
    target: str,
    dimension: str = None,
    domain: str = "",
    groups: list = None,
) -> dict:
    groups = groups if groups is not None else keyword_groups(dimension)
    parts = [str(target or "").strip()]
    if domain:
        parts.append(str(domain).strip())
    parts.extend(flatten_words(groups)[:MAX_QUERY_TERMS])
    return {
        "query": " ".join(dict.fromkeys(part for part in parts if part)),
        "search_depth": "advanced",
    }
