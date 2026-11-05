"""PMC3: the "manual info matching" version of PMC for the drug board (counters ES3 / EPMC3)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Non-Clinical Studies')
MODE = "PMC3"

WORDS_LIMIT = getattr(settings, "PMC_WORDS_LIMIT", None) or 4


def base_forms(name):
    from config import drug_forms as _forms
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


INFO_TERMS = {'KT-621': {'target': ['STAT6'],
            'indication': ['atopic dermatitis', 'eosinophilic asthma'],
            'mechanism': ['targeted protein degrader', 'STAT6 degradation', 'E3 ligase']},
 'NTLA-2002': {'target': ['KLKB1', 'prekallikrein'],
               'indication': ['hereditary angioedema', 'bradykinin'],
               'mechanism': ['in vivo CRISPR', 'Cas9', 'lipid nanoparticle', 'hepatocyte']},
 'Sunvozertinib': {'target': ['EGFR', 'exon 20 insertion'],
                   'indication': ['non-small cell lung cancer'],
                   'mechanism': ['irreversible tyrosine kinase inhibitor']},
 'baxdrostat': {'target': ['aldosterone synthase', 'CYP11B2'],
                'indication': ['resistant hypertension', 'hypertension'],
                'mechanism': ['aldosterone inhibition', 'aldosterone synthesis']},
 'Inclisiran': {'target': ['PCSK9'],
                'indication': ['hypercholesterolemia',
                               'atherosclerotic cardiovascular disease'],
                'mechanism': ['siRNA', 'RNA interference', 'GalNAc', 'hepatocyte']},
 'BNT327': {'target': ['PD-L1', 'VEGF-A'],
            'indication': ['non-small cell lung cancer', 'triple-negative breast cancer'],
            'mechanism': ['bispecific antibody', 'conditional activation']},
 'Azenosertib': {'target': ['WEE1'],
                 'indication': ['ovarian cancer', 'solid tumor'],
                 'mechanism': ['kinase inhibitor', 'DNA damage repair']},
 'Zoldonrasib': {'target': ['KRAS', 'G12C', 'RAS'],
                 'indication': ['pancreatic cancer', 'non-small cell lung cancer'],
                 'mechanism': ['GTPase inhibitor', 'oncogenic KRAS']},
 'Ceralasertib': {'target': ['ATR'],
                  'indication': ['ovarian cancer', 'non-small cell lung cancer'],
                  'mechanism': ['kinase inhibitor', 'DNA damage response']},
 'REX-8756': {'target': ['STAT6'],
              'indication': ['atopic dermatitis'],
              'mechanism': ['small molecule inhibitor']},
 'LNK009': {'target': ['STAT6', 'IL-23'],
            'indication': ['asthma', 'atopic dermatitis'],
            'mechanism': ['PROTAC', 'protein degrader']},
 'ENV-294': {'target': ['JAK1'],
             'indication': ['atopic dermatitis'],
             'mechanism': ['oral kinase inhibitor']},
 'lonvo-z': {'target': ['KLKB1'],
             'indication': ['hereditary angioedema'],
             'mechanism': ['in vivo CRISPR', 'lipid nanoparticle']},
 'Takhzyro': {'target': ['plasma kallikrein'],
              'indication': ['hereditary angioedema'],
              'mechanism': ['monoclonal antibody', 'subcutaneous']},
 'Andembry': {'target': ['factor XIIa'],
              'indication': ['hereditary angioedema'],
              'mechanism': ['monoclonal antibody', 'subcutaneous']},
 'Dawnzera': {'target': ['prekallikrein'],
              'indication': ['hereditary angioedema'],
              'mechanism': ['antisense oligonucleotide']},
 'zipalertinib': {'target': ['EGFR', 'exon 20 insertion'],
                  'indication': ['non-small cell lung cancer'],
                  'mechanism': ['irreversible tyrosine kinase inhibitor']},
 'REZILIENT3': {'target': ['EGFR', 'exon 20 insertion'],
                'indication': ['non-small cell lung cancer'],
                'mechanism': ['tyrosine kinase inhibitor', 'chemotherapy']},
 'BaxHTN': {'target': ['aldosterone synthase'],
            'indication': ['resistant hypertension'],
            'mechanism': ['oral inhibitor']},
 'Lorundrostat': {'target': ['aldosterone synthase'],
                  'indication': ['resistant hypertension'],
                  'mechanism': ['oral inhibitor']},
 'Evolocumab': {'target': ['PCSK9'],
                'indication': ['hypercholesterolemia'],
                'mechanism': ['monoclonal antibody', 'subcutaneous']},
 'Alirocumab': {'target': ['PCSK9'],
                'indication': ['hypercholesterolemia'],
                'mechanism': ['monoclonal antibody', 'subcutaneous']},
 'SSGJ-707': {'target': ['PD-1', 'VEGF'],
              'indication': ['endometrial cancer', 'non-small cell lung cancer'],
              'mechanism': ['bispecific antibody']},
 'HB0025': {'target': ['VEGF'],
            'indication': ['renal cell carcinoma'],
            'mechanism': ['VEGF trap', 'fusion protein']},
 'LM-299': {'target': ['PD-1', 'VEGF'],
            'indication': ['solid tumor'],
            'mechanism': ['trispecific antibody']},
 'MIRV': {'target': ['folate receptor alpha'],
          'indication': ['ovarian cancer'],
          'mechanism': ['antibody-drug conjugate']},
 'AURELIA': {'target': ['VEGF-A'],
             'indication': ['ovarian cancer'],
             'mechanism': ['bevacizumab', 'monoclonal antibody']},
 'GFH375/VS-7375': {'target': ['KRAS', 'G12C'],
                    'indication': ['non-small cell lung cancer'],
                    'mechanism': ['tri-complex inhibitor']},
 'HRS-4642': {'target': ['KRAS', 'G12D'],
              'indication': ['pancreatic cancer'],
              'mechanism': ['covalent inhibitor', 'non-covalent']},
 'INCB161734': {'target': ['KRAS', 'G12D'],
                'indication': ['solid tumor'],
                'mechanism': ['covalent inhibitor']},
 'Berzosertib': {'target': ['ATR'],
                 'indication': ['solid tumor'],
                 'mechanism': ['kinase inhibitor']},
 'Elimusertib': {'target': ['ATR'],
                 'indication': ['solid tumor'],
                 'mechanism': ['kinase inhibitor']}}

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
