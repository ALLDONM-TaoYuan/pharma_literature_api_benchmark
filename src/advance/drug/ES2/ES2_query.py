"""ES2: validation script for ES search with manual alias expansion (drug project)."""


import pathlib
import re
import sys


import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("drug", "ES2")

from config import ES_query as base_es
from config import drug_forms, quoted_phrase, settings

TABLES = ("approved drugs.xlsx", "unapproved drugs.xlsx")
NAME_COLUMN = 1
DOMAIN_COLUMN = 3
DIMENSIONS = ("Basic Information", "Clinical Studies", "Non-Clinical Studies")


ALIASES = {

    "KT-621": ["KT-621", "KT621", "Kymera", "STAT6 degrader"],
    "NTLA-2002": ["NTLA-2002", "NTLA2002", "lonvoguran ziclumeran", "lonvo-z", "Intellia", "CRISPR KLKB1"],
    "Sunvozertinib": ["Sunvozertinib", "DZD9008", "suzetertinib", "Zegfrovy", "Dizal", "EGFR exon 20"],
    "baxdrostat": ["baxdrostat", "CIN-107", "AstraZeneca", "aldosterone synthase inhibitor"],
    "Inclisiran": ["Inclisiran", "ALN-PCSSC", "Leqvio", "Alnylam", "Novartis", "PCSK9 siRNA"],
    "BNT327": ["BNT327", "BMS-986365", "Bristol Myers Squibb"],
    "Azenosertib": ["Azenosertib", "ZN-c3", "Zentalis", "AURORA"],
    "Zoldonrasib": ["Zoldonrasib", "elironrasib", "RMC-6236", "Revolution Medicines"],
    "Ceralasertib": ["Ceralasertib", "AZD6738", "ATR inhibitor", "AstraZeneca"],

    "REX-8756": ["REX-8756", "REX 8756", "Recludix", "STAT6 inhibitor"],
    "LNK009": ["LNK009", "LNK-009", "Lynk", "STAT6 PROTAC"],
    "ENV-294": ["ENV-294", "ENV 294", "Enveda", "JAK1 inhibitor"],
    "lonvo-z": ["lonvo-z", "lonvoguran ziclumeran", "NTLA-2002", "CRISPR KLKB1"],
    "Takhzyro": ["Takhzyro", "lanadelumab", "SHP643", "Takeda"],
    "Andembry": ["Andembry", "garadacimab", "CSL Behring", "factor XIIa"],
    "Dawnzera": ["Dawnzera", "donidalorsen", "Ionis", "antisense oligonucleotide"],
    "zipalertinib": ["zipalertinib", "CLN-081", "Daiichi Sankyo", "EGFR exon 20"],
    "REZILIENT3": ["REZILIENT3", "zipalertinib", "CLN-081"],
    "BaxHTN": ["BaxHTN", "baxdrostat", "CIN-107"],
    "Lorundrostat": ["Lorundrostat", "MLS-101", "aldosterone synthase inhibitor"],
    "Evolocumab": ["Evolocumab", "Repatha", "Amgen"],
    "Alirocumab": ["Alirocumab", "Praluent", "Sanofi", "Regeneron"],
    "SSGJ-707": ["SSGJ-707", "SSGJ707", "3SBio"],
    "HB0025": ["HB0025", "HB0025-1", "HanBio"],
    "LM-299": ["LM-299", "MK-2010", "Merck"],
    "MIRV": ["MIRV", "mirvetuximab", "vobramitamab", "MacroGenics"],
    "AURELIA": ["AURELIA", "bevacizumab", "Avastin"],
    "GFH375/VS-7375": ["GFH375", "VS-7375", "GenFleet", "RAS(ON)"],
    "HRS-4642": ["HRS-4642", "HRS4642", "Hengrui"],
    "INCB161734": ["INCB161734", "Incyte", "G12D inhibitor"],
    "Berzosertib": ["Berzosertib", "M6620", "VX-970", "Merck KGaA"],
    "Elimusertib": ["Elimusertib", "BAY1895344", "Bayer"],
}


KEYWORDS = {
    "Basic Information": [["inhibitor", "degrader", "antibody", "small molecule"]],
    "Clinical Studies": [["clinical trial", "efficacy"]],
    "Non-Clinical Studies": [["in vivo", "in vitro", "cell line", "mouse model"]],
}


REQUEST_EXTRA = {}

RESERVED = re.compile(r'[^0-9A-Za-z]')

def es_phrase(word: str) -> str:
    text = str(word or "").strip()
    if not text:
        return ""
    if RESERVED.search(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def entities() -> list:
    import openpyxl

    names = []
    for table in TABLES:
        path = DATA.parent / table
        if not path.exists():
            continue
        workbook = openpyxl.load_workbook(path, data_only=True)
        for sheet_name in workbook.sheetnames:
            name = str(workbook[sheet_name].cell(2, NAME_COLUMN).value or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def domain_of(entity: str) -> str:
    import openpyxl

    for table in TABLES:
        path = DATA.parent / table
        if not path.exists():
            continue
        workbook = openpyxl.load_workbook(path, data_only=True)
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            if str(sheet.cell(2, NAME_COLUMN).value or "").strip() == entity:
                return str(sheet.cell(2, DOMAIN_COLUMN).value or "").strip()
    return ""


def aliases_of(entity: str) -> list:
    words = list(ALIASES.get(entity) or [])
    if not words:
        words = [entity, *drug_forms(entity)]
    return list(dict.fromkeys(word for word in words if str(word).strip()))


def keyword_groups(dimension: str) -> list:
    return [{"raw": " OR ".join(words), "words": list(words)} for words in KEYWORDS.get(dimension, [])]


def first_group(dimension: str) -> list:
    for group in keyword_groups(dimension):
        if group["words"]:
            return group["words"]
    return []

def build_query_text(entity: str, dimension: str = None, aliases: list = None) -> str:
    names = list(aliases) if aliases is not None else aliases_of(entity)
    anchor = " OR ".join(quoted_phrase(name) for name in names if str(name).strip())
    body = " OR ".join(es_phrase(word) for word in first_group(dimension))
    if anchor and body:
        return f"({anchor}) AND ({body})"
    return f"({anchor})" if anchor else f"({body})"


def build_payload(entity: str, dimension: str = None, aliases: list = None, size: int = None) -> dict:
    payload = {
        "query": {
            "query_string": {
                "fields": list(settings.ES_SEARCH_FIELDS),
                "query": build_query_text(entity, dimension, aliases),
            }
        },
        "_source": list(settings.ES_SOURCE_FIELDS),
        "size": size or settings.TOP_N,
        "track_total_hits": True,
    }
    payload.update(REQUEST_EXTRA)
    return payload


def build_baseline_payload(entity: str, dimension: str = None) -> dict:
    return base_es.build_payload(entity, dimension, groups=base_es.keyword_groups(dimension))


def es_search(payload: dict, size: int = 10) -> dict:
    url = f"{settings.ES_URL.rstrip('/')}/{settings.ES_INDEX}/_search"
    body = dict(payload)
    body["size"] = size
    response = requests.post(
        url, json=body, auth=(settings.ES_USER, settings.ES_PASSWORD),
        timeout=60, proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


def summarize(data: dict) -> tuple:
    total = ((data.get("hits") or {}).get("total") or {}).get("value", 0)
    hits = (data.get("hits") or {}).get("hits") or []
    return total, hits


def show_hits(hits: list, limit: int = 8) -> None:
    for hit in hits[:limit]:
        hit.get("_source") or {}


def compare(entity: str, dimension: str) -> None:
    base_payload = build_baseline_payload(entity, dimension)
    new_payload = build_payload(entity, dimension)
    base_total, base_hits = summarize(es_search(base_payload))
    new_total, new_hits = summarize(es_search(new_payload))
    key = lambda hit: str((hit.get("_source") or {}).get("doi") or hit.get("_id"))
    base_dois = {key(hit) for hit in base_hits}
    new_dois = {key(hit) for hit in new_hits}


    only_new = [hit for hit in new_hits if key(hit) in (new_dois - base_dois)]
    if only_new:
        show_hits(only_new)


def run(entity: str, dimension: str = "Basic Information") -> None:
    payload = build_payload(entity, dimension)
    total, hits = summarize(es_search(payload))


    show_hits(hits)


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        for name in entities():
            pass
        return
    entity = argv[0]
    dimension = argv[1] if len(argv) > 1 and argv[1] in DIMENSIONS else DIMENSIONS[0]
    if "--compare" in argv:
        compare(entity, dimension)
    else:
        run(entity, dimension)


def single_query_text(alias: str, dimension: str = None) -> str:
    anchor = quoted_phrase(alias)
    body = " OR ".join(es_phrase(word) for word in first_group(dimension)[: settings.ES_WORDS_LIMIT])
    if anchor and body:
        return f"({anchor}) AND ({body})"
    return f"({anchor})" if anchor else f"({body})"


def build_round_payloads(entity: str, dimension: str = None, aliases: list = None, size: int = None) -> list:
    names = list(aliases) if aliases is not None else aliases_of(entity)
    payloads = []
    for name in names:
        if not str(name).strip():
            continue
        payload = {
            "query": {
                "query_string": {
                    "fields": list(settings.ES_SEARCH_FIELDS),
                    "query": single_query_text(name, dimension),
                }
            },
            "_source": list(settings.ES_SOURCE_FIELDS),
            "size": size or settings.TOP_N,
            "track_total_hits": True,
        }
        payload.update(REQUEST_EXTRA)
        payloads.append(payload)
    return payloads


def run_rounds(entity: str, dimension: str = None, size: int = 10) -> tuple:
    rounds, merged, seen, total_sum = [], [], set(), 0
    for payload in build_round_payloads(entity, dimension):
        data = es_search(payload, size=size)
        total, hits = summarize(data)
        total_sum += total
        rounds.append({
            "query": payload["query"]["query_string"]["query"],
            "total": total,
            "fetched": len(hits),
        })
        for hit in hits:
            key = str((hit.get("_source") or {}).get("doi") or hit.get("_id"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    return rounds, total_sum, merged


def compare(entity: str, dimension: str) -> None:
    base_payload = build_baseline_payload(entity, dimension)
    base_total, base_hits = summarize(es_search(base_payload))
    rounds, round_sum, new_hits = run_rounds(entity, dimension)
    key = lambda hit: str((hit.get("_source") or {}).get("doi") or hit.get("_id"))
    base_dois = {key(hit) for hit in base_hits}
    new_dois = {key(hit) for hit in new_hits}


    for item in rounds:
        pass


    only_new = [hit for hit in new_hits if key(hit) in (new_dois - base_dois)]
    if only_new:
        show_hits(only_new)


def run(entity: str, dimension: str = "Basic Information") -> None:
    rounds, round_sum, hits = run_rounds(entity, dimension)

    for item in rounds:
        pass

    show_hits(hits)

if __name__ == "__main__":
    main()
