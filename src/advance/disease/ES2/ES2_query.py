"""ES2: validation script for ES search with manual alias expansion and multi-round recall (disease project)."""


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
DATA = variant_data("disease", "ES2")


from config import ES_query as base_es
from config import disease_forms, quoted_phrase, settings

TABLE = "disease.xlsx"
NAME_COLUMN = 1
DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies")


ALIASES = {
    "HIV-1 AIDS": ["HIV-1 AIDS", "HIV-1", "AIDS", "HIV infection",
                   "acquired immunodeficiency syndrome"],
    "ischemic heart disease": ["ischemic heart disease", "ischaemic heart disease",
                               "coronary heart disease", "coronary artery disease",
                               "chronic coronary syndrome", "ischemic cardiomyopathy"],
    "spinal muscular atrophy": ["spinal muscular atrophy", "SMA", "SMN1",
                                "motor neuron disease", "Werdnig-Hoffmann disease"],
    "EGFR Exon20ins mutation non-small cell lung cancer": [
        "EGFR exon20ins", "EGFR exon 20 insertion", "exon 20 insertion mutation",
        "EGFR exon20ins NSCLC", "non-small cell lung cancer"],
    "Her2-positive breast cancer": ["HER2-positive breast cancer", "HER2", "ERBB2",
                                    "HER2 positive", "breast cancer with HER2 overexpression"],
}


KEYWORDS = {
    "Basic Information": [["epidemiology", "pathogenesis", "classification", "diagnosis"]],
    "Clinical Studies": [["clinical trial", "randomized", "efficacy", "treatment guideline"]],
    "Pre-Clinical Studies": [["in vivo", "in vitro", "cell line", "animal model"]],
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


def aliases_of(entity: str) -> list:
    words = list(ALIASES.get(entity) or [])
    if not words:
        words = [entity, *disease_forms(entity)]
    return list(dict.fromkeys(word for word in words if str(word).strip()))


def ladder_forms(entity: str) -> list:
    forms = []
    for label, items in base_es.anchor_tiers(entity) or []:
        for item in items or []:
            if str(item).strip() and item not in forms:
                forms.append(item)
    return forms


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
    body = " OR ".join(es_phrase(word) for word in first_group(dimension)[: settings.ES_WORDS_LIMIT])
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
    return base_es.build_payload(entity, dimension, size=settings.TOP_N)


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


def single_query_text(alias: str, dimension: str = None) -> str:
    anchor = quoted_phrase(alias)
    body = " OR ".join(es_phrase(word) for word in first_group(dimension)[: settings.ES_WORDS_LIMIT])
    if anchor and body:
        return f"({anchor}) AND ({body})"
    return f"({anchor})" if anchor else f"({body})"


def build_round_payloads(entity: str, dimension: str = None, aliases: list = None, size: int = None) -> list:
    names = list(aliases) if aliases is not None else aliases_of(entity)
    for form in ladder_forms(entity):
        if form not in names:
            names.append(form)
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
