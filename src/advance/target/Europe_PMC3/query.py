"""Europe_PMC3: the "manual info matching" version of Europe PMC (counters ES3).. """
from config import Europe_PMC_query, flatten_words, phrase, target_terms

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")
MODE = "Europe_PMC3"


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


INFO_MODE = "AND"

NARROW_IN_ALL_ROUNDS = False


def base_forms(target):
    words = target_terms(target) or [target]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def info_groups(target):
    groups = dict(INFO_TERMS.get(target) or {})
    groups.pop("_mode", None)
    return groups


def anchor_text(target):
    return " OR ".join(phrase(word) for word in base_forms(target))


def keyword_body(dimension):
    return " OR ".join(
        phrase(word) for word in flatten_words(Europe_PMC_query.keyword_groups(dimension))
    )


def build_round_queries(target, dimension, domain=""):
    anchor = anchor_text(target)
    body = keyword_body(dimension)
    baseline = f"({anchor})"
    if body:
        baseline += f" AND ({body})"
    rounds = [{"label": "baseline query", "query": baseline}]

    for label, words in info_groups(target).items():
        items = [phrase(word) for word in words or [] if str(word).strip()]
        if not items:
            continue
        group = "(" + " OR ".join(items) + ")"
        if INFO_MODE == "OR":
            query = f"({anchor} OR {group[1:-1]})"
            if body:
                query += f" AND ({body})"
        else:
            query = f"({anchor}) AND {group}"
            if body and NARROW_IN_ALL_ROUNDS:
                query += f" AND ({body})"
        rounds.append({"label": f"info: {label}", "query": query})
    return rounds
