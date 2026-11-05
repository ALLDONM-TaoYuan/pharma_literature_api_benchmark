"""PMC3: the "manual info matching" version of PMC for the target board (counters ES3 / EPMC3)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies', 'Druggability Feasibility Study')
MODE = "PMC3"

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


def info_groups(name):
    return _info_groups(name)


def build_round_queries(name, dimension, groups):
    body = keyword_body(groups)
    forms = base_forms(name)
    rounds = []
    for form in forms:
        term = f"({quoted_phrase(form)}[AllFields])"
        if body:
            term += f" AND ({body})"
        rounds.append({"label": f"baseline query |{form}", "pmc_term": term, "epmc_term": None})

    primary = forms[0] if forms else name
    for label, words in info_groups(name).items():
        items = [phrase(word) for word in words or [] if str(word).strip()]
        if not items:
            continue
        group = "(" + " OR ".join(f"{item}[AllFields]" for item in items) + ")"
        if INFO_MODE == "OR":
            term = f"({quoted_phrase(primary)}[AllFields] OR {group[1:-1]})"
            if body:
                term += f" AND ({body})"
        else:
            term = f"({quoted_phrase(primary)}[AllFields]) AND {group}"
            if body and NARROW_IN_ALL_ROUNDS:
                term += f" AND ({body})"
        rounds.append({"label": f"info: {label}", "pmc_term": term, "epmc_term": None})
    return rounds
