"""PMC4: the "manual alias plus info" two-track version of PMC for the drug board (counters ES4 / EPMC4)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Non-Clinical Studies')
MODE = "PMC4"

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

ALIASES = {'KT-621': ['KT-621', 'KT621', 'Kymera', 'STAT6 degrader'],
 'NTLA-2002': ['NTLA-2002',
               'NTLA2002',
               'lonvoguran ziclumeran',
               'lonvo-z',
               'Intellia',
               'CRISPR KLKB1'],
 'Sunvozertinib': ['Sunvozertinib',
                   'DZD9008',
                   'suzetertinib',
                   'Zegfrovy',
                   'Dizal',
                   'EGFR exon 20'],
 'baxdrostat': ['baxdrostat', 'CIN-107', 'AstraZeneca', 'aldosterone synthase inhibitor'],
 'Inclisiran': ['Inclisiran', 'ALN-PCSSC', 'Leqvio', 'Alnylam', 'Novartis', 'PCSK9 siRNA'],
 'BNT327': ['BNT327', 'BMS-986365', 'Bristol Myers Squibb'],
 'Azenosertib': ['Azenosertib', 'ZN-c3', 'Zentalis', 'AURORA'],
 'Zoldonrasib': ['Zoldonrasib', 'elironrasib', 'RMC-6236', 'Revolution Medicines'],
 'Ceralasertib': ['Ceralasertib', 'AZD6738', 'ATR inhibitor', 'AstraZeneca'],
 'REX-8756': ['REX-8756', 'REX 8756', 'Recludix', 'STAT6 inhibitor'],
 'LNK009': ['LNK009', 'LNK-009', 'Lynk', 'STAT6 PROTAC'],
 'ENV-294': ['ENV-294', 'ENV 294', 'Enveda', 'JAK1 inhibitor'],
 'lonvo-z': ['lonvo-z', 'lonvoguran ziclumeran', 'NTLA-2002', 'CRISPR KLKB1'],
 'Takhzyro': ['Takhzyro', 'lanadelumab', 'SHP643', 'Takeda'],
 'Andembry': ['Andembry', 'garadacimab', 'CSL Behring', 'factor XIIa'],
 'Dawnzera': ['Dawnzera', 'donidalorsen', 'Ionis', 'antisense oligonucleotide'],
 'zipalertinib': ['zipalertinib', 'CLN-081', 'Daiichi Sankyo', 'EGFR exon 20'],
 'REZILIENT3': ['REZILIENT3', 'zipalertinib', 'CLN-081'],
 'BaxHTN': ['BaxHTN', 'baxdrostat', 'CIN-107'],
 'Lorundrostat': ['Lorundrostat', 'MLS-101', 'aldosterone synthase inhibitor'],
 'Evolocumab': ['Evolocumab', 'Repatha', 'Amgen'],
 'Alirocumab': ['Alirocumab', 'Praluent', 'Sanofi', 'Regeneron'],
 'SSGJ-707': ['SSGJ-707', 'SSGJ707', '3SBio'],
 'HB0025': ['HB0025', 'HB0025-1', 'HanBio'],
 'LM-299': ['LM-299', 'MK-2010', 'Merck'],
 'MIRV': ['MIRV', 'mirvetuximab', 'vobramitamab', 'MacroGenics'],
 'AURELIA': ['AURELIA', 'bevacizumab', 'Avastin'],
 'GFH375/VS-7375': ['GFH375', 'VS-7375', 'GenFleet', 'RAS(ON)'],
 'HRS-4642': ['HRS-4642', 'HRS4642', 'Hengrui'],
 'INCB161734': ['INCB161734', 'Incyte', 'G12D inhibitor'],
 'Berzosertib': ['Berzosertib', 'M6620', 'VX-970', 'Merck KGaA'],
 'Elimusertib': ['Elimusertib', 'BAY1895344', 'Bayer']}

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
