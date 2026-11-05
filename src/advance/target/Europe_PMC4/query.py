"""Europe_PMC4: the "manual alias plus info" two-track version of Europe PMC (counters ES4).. """
from config import Europe_PMC_query, flatten_words, phrase, target_terms

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")
MODE = "Europe_PMC4"

ALIASES = {
    "BRIP1/DHX9": ["BRIP1", "DHX9", "BRIP1/DHX9", "RNA helicase", "BRIP1-DHX9"],
    "HIV-1 capsid": ["HIV-1 capsid", "HIV-1", "capsid", "CA", "p24", "HIV capsid"],
    "ROCK": ["ROCK", "Rho kinase", "Rho-associated kinase", "ROCK1", "ROCK2"],
    "JAK1": ["JAK1", "Janus kinase 1", "JAK-1"],
    "IL-17A IL-17F": ["IL-17A", "IL-17F", "IL-17", "interleukin-17", "IL17A"],
}

INFO_TERMS = {
    "BRIP1/DHX9": {"function": ["RNA helicase", "RNA processing"],
                   "disease": ["small cell lung cancer", "colorectal cancer"],
                   "mechanism": ["RNA splicing", "RNA translation"]},
    "HIV-1 capsid": {"function": ["viral capsid", "CA protein"],
                     "disease": ["HIV infection"],
                     "mechanism": ["viral capsid assembly"]},
    "ROCK": {"function": ["Rho kinase", "cytoskeleton"],
             "disease": ["Crohn's disease"],
             "mechanism": ["actin cytoskeleton", "actin cytoskeleton rearrangement", "fibrosis"]},
    "JAK1": {"function": ["Janus kinase", "cytokine signaling"],
             "disease": ["atopic dermatitis", "rheumatoid arthritis"],
             "mechanism": ["STAT phosphorylation", "JAK-STAT pathway"]},
    "IL-17A IL-17F": {"function": ["interleukin-17", "T helper 17"],
                      "disease": ["plaque psoriasis"],
                      "mechanism": ["neutrophil recruitment", "IL-17A secretion"]},
}

DOMAIN_TERMS = {
    "Small Cell Lung Cancer / Colorectal Cancer": ["small cell lung cancer", "colorectal cancer"],
    "HIV Infection": ["HIV infection"],
    "Crohn's Disease": ["Crohn's disease"],
    "Atopic Dermatitis / Rheumatoid Arthritis": ["atopic dermatitis", "rheumatoid arthritis"],
    "Plaque Psoriasis": ["plaque psoriasis"],
}
DOMAIN_DIMENSIONS = ("Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")
USE_DOMAIN = False

INFO_MODE = "AND"
NARROW_IN_ALL_ROUNDS = False


def aliases_of(target):
    words = list(ALIASES.get(target) or [])
    if not words:
        words = target_terms(target) or [target]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def info_groups(target):
    groups = dict(INFO_TERMS.get(target) or {})
    groups.pop("_mode", None)
    return groups


def domain_terms(domain, dimension=None):
    if not USE_DOMAIN:
        return []
    if dimension and dimension not in DOMAIN_DIMENSIONS:
        return []
    return list(DOMAIN_TERMS.get(str(domain or "").strip(), []))


def keyword_body(dimension):
    return " OR ".join(
        phrase(word) for word in flatten_words(Europe_PMC_query.keyword_groups(dimension))
    )


def build_round_queries(target, dimension, domain=""):
    body = keyword_body(dimension)
    domains = domain_terms(domain, dimension)
    domain_clause = (
        " AND (" + " OR ".join(phrase(word) for word in domains) + ")" if domains else ""
    )
    rounds = []
    groups = list(info_groups(target).items())
    for alias in aliases_of(target):
        anchor = f"({phrase(alias)})"
        baseline = anchor + (f" AND ({body})" if body else "") + domain_clause
        rounds.append({"label": f"{alias} | baseline", "query": baseline})
        for label, words in groups:
            items = [phrase(word) for word in words or [] if str(word).strip()]
            if not items:
                continue
            group = "(" + " OR ".join(items) + ")"
            if INFO_MODE == "OR":
                query = f"({phrase(alias)} OR {group[1:-1]})"
                if body:
                    query += f" AND ({body})"
                query += domain_clause
            else:
                query = f"{anchor} AND {group}"
                if body and NARROW_IN_ALL_ROUNDS:
                    query += f" AND ({body})"
                query += domain_clause
            rounds.append({"label": f"{alias}｜info:{label}", "query": query})
    return rounds
