"""API input conventions for the openFDA interface (this interface's field mappings and request parameters are maintained here)."""

from config import phrase

OPENFDA_FIELDS_BY_DIMENSION = {
    "Basic Information": ("mechanism_of_action",),
    "Clinical Studies": ("clinical_pharmacology",),
    "Pre-Clinical Studies": ("nonclinical_toxicology",),
    "Druggability Feasibility Study": ("mechanism_of_action", "description"),
}


OPENFDA_DEFAULT_FIELDS = ("mechanism_of_action",)


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


def fields_for_dimension(dimension: str) -> tuple:
    return OPENFDA_FIELDS_BY_DIMENSION.get(dimension, OPENFDA_DEFAULT_FIELDS)


def build_params(terms: list, dimension: str = None, groups: list = None) -> dict:
    body = " OR ".join(phrase(term) for term in (terms or []))
    search = " OR ".join(f"{field}:({body})" for field in fields_for_dimension(dimension))
    return {"search": search, "limit": None}
