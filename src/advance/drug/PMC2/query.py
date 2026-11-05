"""PMC2: the "manual alias, multi-round" version of PMC for the drug board (counters ES2 / EPMC2)"""

from config import phrase, settings

try:
    from config import quoted_phrase
except ImportError:
    quoted_phrase = phrase

DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Non-Clinical Studies')
MODE = "PMC2"

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
