"""Query script for the Europe PMC interface (this interface's keyword groups and query strings are maintained here)."""

from config import flatten_words, phrase


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


def build_target_query(terms: list, dimension: str = None, groups: list = None) -> str:
    groups = groups if groups is not None else keyword_groups(dimension)
    anchor = " OR ".join(phrase(term) for term in (terms or []))
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
