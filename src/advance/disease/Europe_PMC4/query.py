"""Europe_PMC4: the "manual alias plus info" two-track version of Europe PMC (counters ES4)."""

from config import disease_forms, disease_keyword_groups, flatten_words, phrase, quoted_phrase

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies")
MODE = "Europe_PMC4"
FORCE_QUOTES = False

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


def aliases_of(disease):
    words = list(ALIASES.get(disease) or [])
    if not words:
        words = disease_forms(disease) or [disease]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def ladder_forms(disease):
    from config import ES_query
    forms = []
    try:
        tiers = ES_query.anchor_tiers(disease) or []
    except Exception:
        tiers = []
    for _label, items in tiers:
        for item in items or []:
            text = str(item).strip()
            if text and text not in forms:
                forms.append(text)
    return forms


def info_groups(disease):
    groups = dict(INFO_TERMS.get(disease) or {})
    groups.pop("_mode", None)
    return groups


def anchor_text(term):
    text = str(term or "").strip()
    return quoted_phrase(text) if FORCE_QUOTES else text


def keyword_body(dimension):
    return " OR ".join(
        phrase(word) for word in flatten_words(disease_keyword_groups(dimension))
    )


def build_round_queries(disease, dimension, domain=""):
    body = keyword_body(dimension)
    names = aliases_of(disease)
    names += [form for form in ladder_forms(disease) if form not in names]
    rounds = []
    for name in names:
        anchor = f"({anchor_text(name)})"
        baseline = anchor + (f" AND ({body})" if body else "")
        rounds.append({"label": f"{name} | baseline", "query": baseline})
        for label, words in info_groups(disease).items():
            items = [phrase(word) for word in words or [] if str(word).strip()]
            if not items:
                continue
            group = "(" + " OR ".join(items) + ")"
            if INFO_MODE == "OR":
                query = f"({anchor_text(name)} OR {group[1:-1]})"
                if body:
                    query += f" AND ({body})"
            else:
                query = f"{anchor} AND {group}"
                if body and NARROW_IN_ALL_ROUNDS:
                    query += f" AND ({body})"
            rounds.append({"label": f"{name} | info: {label}", "query": query})
    return rounds
