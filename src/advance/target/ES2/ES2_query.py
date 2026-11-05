"""ES2: validation script for ES search with manual alias expansion and multi-round recall (target project)."""


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
DATA = variant_data("target", "ES2")


from config import ES_query as base_es
from config import settings, target_terms

TABLE = "target.xlsx"
NAME_COLUMN = 1
DOMAIN_COLUMN = 2
DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")


ALIASES = {
    "BRIP1/DHX9": ["BRIP1", "DHX9", "BRIP1/DHX9", "RNA helicase", "BRIP1-DHX9"],
    "HIV-1 capsid": ["HIV-1 capsid", "HIV-1", "capsid", "CA", "p24", "HIV capsid"],
    "ROCK": ["ROCK", "Rho kinase", "Rho-associated kinase", "ROCK1", "ROCK2"],
    "JAK1": ["JAK1", "Janus kinase 1", "JAK-1"],
    "IL-17A IL-17F": ["IL-17A", "IL-17F", "IL-17", "interleukin-17", "IL17A"],
}


KEYWORDS = {
    "Basic Information": [["gene", "protein"], ["mechanism", "pathway"]],
    "Clinical Studies": [["clinical trial"]],
    "Pre-Clinical Studies": [["in vivo", "in vitro", "cell line", "mouse model"]],
    "Druggability Feasibility Study": [["inhibitor"]],
}


DOMAIN_TERMS = {
    "Small Cell Lung Cancer / Colorectal Cancer": ["small cell lung cancer", "colorectal cancer"],
    "HIV Infection": ["HIV infection"],
    "Crohn's Disease": ["Crohn's disease"],
    "Atopic Dermatitis / Rheumatoid Arthritis": ["atopic dermatitis", "rheumatoid arthritis"],
    "Plaque Psoriasis": ["plaque psoriasis"],
}
DOMAIN_DIMENSIONS = ("Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")


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

    path = DATA.parent / TABLE
    if not path.exists():
        return []
    workbook = openpyxl.load_workbook(path, data_only=True)
    names = []
    for sheet_name in workbook.sheetnames:
        name = str(workbook[sheet_name].cell(2, NAME_COLUMN).value or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def domain_of(entity: str) -> str:
    import openpyxl

    path = DATA.parent / TABLE
    if not path.exists():
        return ""
    workbook = openpyxl.load_workbook(path, data_only=True)
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        if str(sheet.cell(2, NAME_COLUMN).value or "").strip() == entity:
            return str(sheet.cell(2, DOMAIN_COLUMN).value or "").strip()
    return ""


def aliases_of(entity: str) -> list:
    words = list(ALIASES.get(entity) or [])
    if not words:
        words = target_terms(entity) or [entity]
    return list(dict.fromkeys(word for word in words if str(word).strip()))


def keyword_groups(dimension: str) -> list:
    return [{"raw": " OR ".join(words), "words": list(words)} for words in KEYWORDS.get(dimension, [])]


def domain_terms(domain: str, dimension: str = None) -> list:
    if dimension and dimension not in DOMAIN_DIMENSIONS:
        return []
    return list(DOMAIN_TERMS.get(str(domain or "").strip(), []))


def build_query_text(entity: str, dimension: str = None, aliases: list = None, domain: str = None) -> str:
    names = list(aliases) if aliases is not None else aliases_of(entity)
    domain = domain_of(entity) if domain is None else domain
    anchor = "(" + " OR ".join(es_phrase(name) for name in names if str(name).strip()) + ")"
    clauses = []
    for group in keyword_groups(dimension):
        words = group["words"][: settings.ES_WORDS_LIMIT]
        if words:
            clauses.append("(" + " OR ".join(es_phrase(word) for word in words) + ")")
    domains = domain_terms(domain, dimension)
    if domains:
        clauses.append("(" + " OR ".join(es_phrase(word) for word in domains) + ")")
    return " AND ".join([anchor] + clauses) if clauses else anchor


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
    return base_es.build_payload(
        target_terms(entity), dimension,
        groups=base_es.keyword_groups(dimension), domain=domain_of(entity),
    )


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
    return total, (data.get("hits") or {}).get("hits") or []


def show_hits(hits: list, limit: int = 8) -> None:
    for hit in hits[:limit]:
        hit.get("_source") or {}


def single_query_text(alias: str, dimension: str = None, domain: str = None) -> str:
    anchor = "(" + es_phrase(alias) + ")"
    clauses = []
    for group in keyword_groups(dimension):
        words = group["words"][: settings.ES_WORDS_LIMIT]
        if words:
            clauses.append("(" + " OR ".join(es_phrase(word) for word in words) + ")")
    domains = domain_terms(domain, dimension)
    if domains:
        clauses.append("(" + " OR ".join(es_phrase(word) for word in domains) + ")")
    return " AND ".join([anchor] + clauses) if clauses else anchor


def build_round_payloads(entity: str, dimension: str = None, aliases: list = None, size: int = None) -> list:
    names = list(aliases) if aliases is not None else aliases_of(entity)
    domain = domain_of(entity)
    payloads = []
    for name in names:
        if not str(name).strip():
            continue
        payload = {
            "query": {
                "query_string": {
                    "fields": list(settings.ES_SEARCH_FIELDS),
                    "query": single_query_text(name, dimension, domain),
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


if __name__ == "__main__":
    main()
