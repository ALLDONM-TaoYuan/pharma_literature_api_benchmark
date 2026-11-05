"""Europe_PMC2: the "manual alias, multi-round" version of Europe PMC (counters ES2)."""

from config import disease_keyword_groups, flatten_words, phrase, quoted_phrase

DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies")
MODE = "Europe_PMC2"
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


def aliases_of(disease):
    words = list(ALIASES.get(disease) or []) or [disease]
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


def anchor_text(term):
    text = str(term or "").strip()
    return quoted_phrase(text) if FORCE_QUOTES else text


def keyword_body(dimension):
    return " OR ".join(
        phrase(word) for word in flatten_words(disease_keyword_groups(dimension))
    )


def build_round_queries(disease, dimension, domain=""):
    body = keyword_body(dimension)
    rounds = []
    names = aliases_of(disease)
    names += [form for form in ladder_forms(disease) if form not in names]
    for name in names:
        query = f"({anchor_text(name)})"
        if body:
            query += f" AND ({body})"
        rounds.append({"label": name, "query": query})
    return rounds
