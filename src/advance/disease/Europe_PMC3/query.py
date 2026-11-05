"""Europe_PMC3: the "manual info matching" version of Europe PMC (counters ES3)."""

from config import disease_forms, disease_keyword_groups, flatten_words, phrase, quoted_phrase

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies")
MODE = "Europe_PMC3"
FORCE_QUOTES = False


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


def base_forms(disease):
    words = disease_forms(disease) or [disease]
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


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
    forms = base_forms(disease)
    rounds = []
    for name in forms:
        query = f"({anchor_text(name)})"
        if body:
            query += f" AND ({body})"
        rounds.append({"label": f"baseline query |{name}", "query": query})

    primary = forms[0] if forms else disease
    for label, words in info_groups(disease).items():
        items = [phrase(word) for word in words or [] if str(word).strip()]
        if not items:
            continue
        group = "(" + " OR ".join(items) + ")"
        if INFO_MODE == "OR":
            query = f"({anchor_text(primary)} OR {group[1:-1]})"
            if body:
                query += f" AND ({body})"
        else:
            query = f"({anchor_text(primary)}) AND {group}"
            if body and NARROW_IN_ALL_ROUNDS:
                query += f" AND ({body})"
        rounds.append({"label": f"info: {label}", "query": query})
    return rounds
