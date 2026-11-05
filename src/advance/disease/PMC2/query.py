"""PMC2: the "manual alias, multi-round" version of PMC for the disease board (counters ES2 / EPMC2)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies')
MODE = "PMC2"

WORDS_LIMIT = getattr(settings, "PMC_WORDS_LIMIT", None) or 4


def base_forms(name):
    from config import disease_forms as _forms
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


ALIASES = {'HIV-1 AIDS': ['HIV-1 AIDS',
                'HIV-1',
                'AIDS',
                'HIV infection',
                'acquired immunodeficiency syndrome'],
 'ischemic heart disease': ['ischemic heart disease',
                            'ischaemic heart disease',
                            'coronary heart disease',
                            'coronary artery disease',
                            'chronic coronary syndrome',
                            'ischemic cardiomyopathy'],
 'spinal muscular atrophy': ['spinal muscular atrophy',
                             'SMA',
                             'SMN1',
                             'motor neuron disease',
                             'Werdnig-Hoffmann disease'],
 'EGFR Exon20ins mutation non-small cell lung cancer': ['EGFR exon20ins',
                                                        'EGFR exon 20 insertion',
                                                        'exon 20 insertion mutation',
                                                        'EGFR exon20ins NSCLC',
                                                        'non-small cell lung cancer'],
 'Her2-positive breast cancer': ['HER2-positive breast cancer',
                                 'HER2',
                                 'ERBB2',
                                 'HER2 positive',
                                 'breast cancer with HER2 overexpression']}


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
