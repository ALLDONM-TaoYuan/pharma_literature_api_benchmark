"""PMC3: the "manual info matching" version of PMC for the disease board (counters ES3 / EPMC3)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies')
MODE = "PMC3"

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


INFO_TERMS = {'HIV-1 AIDS': {'cause': ['HIV-1', 'retrovirus', 'CD4 depletion'],
                'manifestation': ['angioedema',
                                  'opportunistic infection',
                                  'CD4 T cell depletion'],
                'mechanism': ['bradykinin', 'plasma kallikrein', 'immune activation']},
 'ischemic heart disease': {'cause': ['atherosclerosis', 'coronary plaque'],
                            'manifestation': ['angina',
                                              'myocardial infarction',
                                              'exertional dyspnea'],
                            'mechanism': ['plaque rupture', 'thrombosis', 'ischemia']},
 'spinal muscular atrophy': {'cause': ['SMN1', 'SMN1 deletion', 'autosomal recessive'],
                             'manifestation': ['muscle weakness', 'motor milestone delay'],
                             'mechanism': ['SMN protein',
                                           'motor neuron degeneration',
                                           'SMN2 splicing']},
 'EGFR Exon20ins mutation non-small cell lung cancer': {'cause': ['EGFR exon 20 insertion',
                                                                  'driver mutation'],
                                                        'manifestation': ['non-small cell lung '
                                                                          'cancer',
                                                                          'brain metastasis'],
                                                        'mechanism': ['tyrosine kinase '
                                                                      'activation',
                                                                      'structural insertion']},
 'Her2-positive breast cancer': {'cause': ['HER2', 'ERBB2', 'amplification'],
                                 'manifestation': ['breast cancer', 'brain metastasis'],
                                 'mechanism': ['receptor dimerization', 'PI3K signaling']}}

INFO_MODE = "AND"
NARROW_IN_ALL_ROUNDS = False


def info_groups(name):
    return _info_groups(name)


LONG_NAME_WORDS = 5


def name_tiers(form: str) -> list:
    words = form.split()
    tiers = [form]
    if len(words) > 2:
        tiers.append(" ".join(words[:3]))
    if len(words) > 1:
        tiers.append(" ".join(words[:2]))
    out = []
    for tier in tiers:
        if tier not in out:
            out.append(tier)
    return out


def is_long_name(form: str) -> bool:
    return len(form.split()) > LONG_NAME_WORDS


def build_round_queries(name, dimension, groups):
    body = keyword_body(groups)
    forms = base_forms(name)
    rounds = []
    for form in forms:
        tiers = name_tiers(form) if is_long_name(form) else [form]
        for tier in tiers:
            term = f"({quoted_phrase(tier)}[AllFields])"
            if body:
                term += f" AND ({body})"
            label = (f"baseline query |{form}" if tier == form
                     else f"baseline query |{form}| fallback:{tier}")
            rounds.append({"label": label, "pmc_term": term, "epmc_term": None})

    primary = forms[0] if forms else name
    if primary and is_long_name(primary):
        primary = name_tiers(primary)[-1]
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
