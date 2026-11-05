"""PMC2: the "manual alias, multi-round" version of PMC for the target board (counters ES2 / EPMC2)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies', 'Druggability Feasibility Study')
MODE = "PMC2"

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


def aliases_of(name):
    words = list(ALIASES.get(name) or [])
    if not words:
        words = [name]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def build_round_queries(name, dimension, groups):
    body = keyword_body(groups)
    rounds = []
    for alias in aliases_of(name):
        term = f"({quoted_phrase(alias)}[AllFields])"
        if body:
            term += f" AND ({body})"
        rounds.append({"label": alias, "pmc_term": term, "epmc_term": None})
    return rounds
