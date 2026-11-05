"""PMC4: the "manual alias plus info" two-track version of PMC for the disease board (counters ES4 / EPMC4)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies')
MODE = "PMC4"

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
