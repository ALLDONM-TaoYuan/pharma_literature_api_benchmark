"""PMC4: the "manual alias plus info" two-track version of PMC for the target board (counters ES4 / EPMC4)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies', 'Druggability Feasibility Study')
MODE = "PMC4"

WORDS_LIMIT = getattr(settings, "PMC_WORDS_LIMIT", None) or 4


def base_forms(name):
    from config import target_terms as _forms
    words = _forms(name) or [name]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def keyword_body(groups):
    words = []
    for group in groups:
        words.extend(group["words"][:WORDS_LIMIT])
    return " OR ".join(f"{phrase(word)}[AllFields]" for word in dict.fromkeys(words))


def _info_groups(name):
    groups = dict(INFO_TERMS.get(name) or {})
    groups.pop("_mode", None)
    return groups

ALIASES = {'BRIP1/DHX9': ['BRIP1', 'DHX9', 'BRIP1/DHX9', 'RNA helicase', 'BRIP1-DHX9'],
 'HIV-1 capsid': ['HIV-1 capsid', 'HIV-1', 'capsid', 'CA', 'p24', 'HIV capsid'],
 'ROCK': ['ROCK', 'Rho kinase', 'Rho-associated kinase', 'ROCK1', 'ROCK2'],
 'JAK1': ['JAK1', 'Janus kinase 1', 'JAK-1'],
 'IL-17A IL-17F': ['IL-17A', 'IL-17F', 'IL-17', 'interleukin-17', 'IL17A']}

INFO_TERMS = {'BRIP1/DHX9': {'function': ['RNA helicase', 'RNA processing'],
                'disease': ['small cell lung cancer', 'colorectal cancer'],
                'mechanism': ['RNA splicing', 'RNA translation']},
 'HIV-1 capsid': {'function': ['viral capsid', 'CA protein'],
                  'disease': ['HIV infection'],
                  'mechanism': ['viral capsid assembly']},
 'ROCK': {'function': ['Rho kinase', 'cytoskeleton'],
          'disease': ["Crohn's disease"],
          'mechanism': ['actin cytoskeleton', 'actin cytoskeleton rearrangement', 'fibrosis']},
 'JAK1': {'function': ['Janus kinase', 'cytokine signaling'],
          'disease': ['atopic dermatitis', 'rheumatoid arthritis'],
          'mechanism': ['STAT phosphorylation', 'JAK-STAT pathway']},
 'IL-17A IL-17F': {'function': ['interleukin-17', 'T helper 17'],
                   'disease': ['plaque psoriasis'],
                   'mechanism': ['neutrophil recruitment', 'IL-17A secretion']}}

INFO_MODE = "AND"
NARROW_IN_ALL_ROUNDS = False


def aliases_of(name):
    words = list(ALIASES.get(name) or [])
    if not words:
        words = base_forms(name) or [name]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def info_groups(name):
    return _info_groups(name)


def build_round_queries(name, dimension, groups):
    body = keyword_body(groups)
    rounds = []
    for alias in aliases_of(name):
        anchor = f"({quoted_phrase(alias)}[AllFields])"
        baseline = anchor + (f" AND ({body})" if body else "")
        rounds.append({"label": f"{alias} | baseline", "pmc_term": baseline, "epmc_term": None})
        for label, words in info_groups(name).items():
            items = [phrase(word) for word in words or [] if str(word).strip()]
            if not items:
                continue
            group = "(" + " OR ".join(f"{item}[AllFields]" for item in items) + ")"
            if INFO_MODE == "OR":
                term = f"({quoted_phrase(alias)}[AllFields] OR {group[1:-1]})"
                if body:
                    term += f" AND ({body})"
            else:
                term = f"{anchor} AND {group}"
                if body and NARROW_IN_ALL_ROUNDS:
                    term += f" AND ({body})"
            rounds.append({"label": f"{alias}｜info:{label}", "pmc_term": term, "epmc_term": None})
    return rounds
