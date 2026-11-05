"""Europe_PMC2: the "manual alias, multi-round" version of Europe PMC (counters ES2).. """
from config import Europe_PMC_query, flatten_words, phrase

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")
MODE = "Europe_PMC2"


ALIASES = {
    "BRIP1/DHX9": ["BRIP1", "DHX9", "BRIP1/DHX9", "RNA helicase", "BRIP1-DHX9"],
    "HIV-1 capsid": ["HIV-1 capsid", "HIV-1", "capsid", "CA", "p24", "HIV capsid"],
    "ROCK": ["ROCK", "Rho kinase", "Rho-associated kinase", "ROCK1", "ROCK2"],
    "JAK1": ["JAK1", "Janus kinase 1", "JAK-1"],
    "IL-17A IL-17F": ["IL-17A", "IL-17F", "IL-17", "interleukin-17", "IL17A"],
}


DOMAIN_TERMS = {
    "Small Cell Lung Cancer / Colorectal Cancer": ["small cell lung cancer", "colorectal cancer"],
    "HIV Infection": ["HIV infection"],
    "Crohn's Disease": ["Crohn's disease"],
    "Atopic Dermatitis / Rheumatoid Arthritis": ["atopic dermatitis", "rheumatoid arthritis"],
    "Plaque Psoriasis": ["plaque psoriasis"],
}
DOMAIN_DIMENSIONS = ("Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")
USE_DOMAIN = True


def aliases_of(target):
    words = list(ALIASES.get(target) or [])
    if not words:
        words = [target]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def domain_terms(domain, dimension=None):
    if not USE_DOMAIN:
        return []
    if dimension and dimension not in DOMAIN_DIMENSIONS:
        return []
    return list(DOMAIN_TERMS.get(str(domain or "").strip(), []))


def keyword_body(dimension):
    groups = Europe_PMC_query.keyword_groups(dimension)
    return " OR ".join(phrase(word) for word in flatten_words(groups))


def build_round_queries(target, dimension, domain=""):
    body = keyword_body(dimension)
    domains = domain_terms(domain, dimension)
    rounds = []
    for alias in aliases_of(target):
        parts = [f"({phrase(alias)})"]
        if body:
            parts.append(f"({body})")
        if domains:
            parts.append("(" + " OR ".join(phrase(word) for word in domains) + ")")
        rounds.append({"label": alias, "query": " AND ".join(parts)})
    return rounds
