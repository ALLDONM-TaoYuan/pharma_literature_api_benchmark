"""Controller: reads the drug test workbooks and collects literature for each sheet's main drug and competitors across all interfaces."""

from __future__ import annotations

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import openpyxl
import requests

from config import (
    DRUG_DIMENSIONS,
    ES_query,
    Europe_PMC_query,
    PMC_query,
    settings,
    tavily_query,
)


import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import board_data  # noqa: E402

BASE_DIR = board_data("drug")


SKIP_TAGS = {
    "ref-list",
    "table-wrap",
    "fig",
    "fig-group",
    "fn-group",
    "supplementary-material",
    "disp-formula",
    "disp-quote",
    "media",
}


ARXIV_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


SOURCES = ("Europe_PMC", "PMC", "ES")


def configured_sources() -> tuple:
    return SOURCES


class ApiCallError(Exception):
    pass


def call_api(
    url: str,
    params: dict = None,
    *,
    method: str = "get",
    payload: dict = None,
    parser: str = "json",
    validate=None,
    timeout=None,
    retry_times=None,
    retry_wait=None,
    auth: tuple = None,
    use_proxy: bool = True,
) -> tuple:
    attempts = retry_times if retry_times is not None else settings.RETRY_TIMES
    wait = retry_wait if retry_wait is not None else settings.RETRY_WAIT_SECONDS
    request_timeout = timeout if timeout is not None else settings.REQUEST_TIMEOUT
    proxies = (
        {"http": settings.PROXY_URL, "https": settings.PROXY_URL}
        if settings.PROXY_URL and use_proxy
        else None
    )
    last_error = ""
    for attempt in range(1, attempts + 1):
        delay = wait
        try:
            if method.lower() == "post":
                if payload is not None:
                    response = requests.post(
                        url,
                        json=payload,
                        timeout=request_timeout,
                        headers={"User-Agent": settings.USER_AGENT},
                        proxies=proxies,
                        auth=auth,
                    )
                else:
                    response = requests.post(
                        url,
                        data=params,
                        timeout=request_timeout,
                        headers={"User-Agent": settings.USER_AGENT},
                        proxies=proxies,
                        auth=auth,
                    )
            else:
                response = requests.get(
                    url,
                    params=params,
                    timeout=request_timeout,
                    headers={"User-Agent": settings.USER_AGENT},
                    proxies=proxies,
                    auth=auth,
                )
            if response.status_code in (429, 503):
                last_error = f"HTTP {response.status_code}(rate limited or service temporarily unavailable)"
                retry_after = str(response.headers.get("Retry-After", "")).strip()
                if retry_after.isdigit():
                    delay = int(retry_after)
            else:
                response.raise_for_status()
                content = response.json() if parser == "json" else response.text
                if validate is not None and not validate(content):
                    last_error = f"Invalid response content: {str(content)[:120]}"
                else:
                    return response.status_code, content
        except ValueError as exc:
            last_error = f"Response is not valid JSON: {exc}"
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            time.sleep(delay)
    raise ApiCallError(f"Failed {attempts} consecutive attempts ({url}): {last_error}")


def save_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def normalize_text(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", str(text).lower())


def match_keywords(text: str, groups: list) -> dict:
    haystack = normalize_text(text)
    matched = []
    hits = {}
    for group in groups:
        found = [word for word in group["words"] if normalize_text(word) in haystack]
        if found:
            matched.append(group["raw"])
            hits[group["raw"]] = found
    ratio = round(len(matched) / len(groups), 3) if groups else 0.0
    return {"matched": matched, "hits": hits, "ratio": ratio}


def to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def content_type_of(abstract: str, full_text: str) -> str:
    if full_text:
        return "full_text"
    return "abstract_only" if abstract else "metadata_only"


def make_result(
    rank: int,
    title: str,
    content: str,
    url: str,
    doi,
    content_type: str,
    abstract_text: str,
    groups: list,
    match_scope: str,
    extra: dict = None,
) -> dict:
    title_abstract = match_keywords(f"{title} {abstract_text}", groups)
    content_match = match_keywords(content, groups)
    result = {
        "rank": rank,
        "title": title,
        "content": content,
        "content_type": content_type,
        "content_length": len(content),
        "url": url,
        "doi": doi,
        "match_scope": match_scope,
        "match_ratio": title_abstract["ratio"],
        "matched_keywords": title_abstract["matched"],
        "matched_terms": title_abstract["hits"],
        "content_match_ratio": content_match["ratio"],
        "content_matched_keywords": content_match["matched"],
    }
    if extra:
        result.update(extra)
    return result


def build_metrics(results: list, groups: list) -> dict:
    hit_counts = {
        group["raw"]: sum(1 for item in results if group["raw"] in item["matched_keywords"])
        for group in groups
    }
    covered = sum(1 for count in hit_counts.values() if count)
    ratios = [item["match_ratio"] for item in results]
    content_ratios = [item["content_match_ratio"] for item in results]
    return {
        "returned_count": len(results),
        "full_text_count": sum(1 for item in results if item["content_type"] == "full_text"),
        "abstract_only_count": sum(
            1 for item in results if item["content_type"] == "abstract_only"
        ),
        "with_doi_count": sum(1 for item in results if item["doi"]),
        "with_url_count": sum(1 for item in results if item["url"]),
        "avg_match_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 0.0,
        "avg_content_match_ratio": (
            round(sum(content_ratios) / len(content_ratios), 3) if content_ratios else 0.0
        ),
        "keyword_coverage": round(covered / len(groups), 3) if groups else 0.0,
        "keyword_hit_counts": hit_counts,
        "gold_hit_count": None,
    }


def build_record(
    unit: dict,
    source: str,
    request: dict,
    status_code,
    total_results: int,
    results: list,
    error=None,
) -> dict:
    keywords = [group["raw"] for group in unit.get("groups", [])]
    return {
        "target": unit["target"],
        "drug": unit["drug"],
        "object": unit.get("name", unit["drug"]),
        "parent_drug": unit.get("parent_drug", unit["drug"]),
        "is_competitor": unit.get("is_competitor", False),
        "domain": unit.get("domain", ""),
        "dimension": unit["dimension"],
        "source": source,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keywords": keywords,
        "split_query": keywords,
        "request": request,
        "status_code": status_code,
        "ok": error is None,
        "error": error,
        "total_results": total_results,
        "returned_results": len(results),
        "metrics": build_metrics(results, unit.get("groups", [])),
        "results": results,
    }


def build_all_result(records: list) -> dict:
    results = []
    for record in records:
        for item in record["results"]:
            results.append({"source": record["source"], **item})
    comparison = {
        "hit_counts": {r["source"]: r["total_results"] for r in records},
        "returned_counts": {r["source"]: r["returned_results"] for r in records},
        "full_text_counts": {r["source"]: r["metrics"]["full_text_count"] for r in records},
        "avg_match_ratio": {r["source"]: r["metrics"]["avg_match_ratio"] for r in records},
        "keyword_coverage": {r["source"]: r["metrics"]["keyword_coverage"] for r in records},
    }
    first = records[0] if records else {}
    return {
        "target": first.get("target", ""),
        "drug": first.get("drug", ""),
        "object": first.get("object", first.get("drug", "")),
        "parent_drug": first.get("parent_drug", first.get("drug", "")),
        "is_competitor": first.get("is_competitor", False),
        "domain": first.get("domain", ""),
        "dimension": first.get("dimension", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keywords": first.get("keywords", first.get("split_query", [])),
        "split_query": first.get("split_query", []),
        "source_status": [
            {
                "source": record["source"],
                "ok": record["ok"],
                "error": record["error"],
                "total_results": record["total_results"],
                "returned_results": record["returned_results"],
                "metrics": record["metrics"],
            }
            for record in records
        ],
        "comparison": comparison,
        "returned_results": len(results),
        "results": results,
    }


def read_competitors(sheet) -> list:
    names = []
    for row in range(settings.COMPETITOR_START_ROW, sheet.max_row + 1):
        value = str(sheet.cell(row, settings.COMPETITOR_COLUMN).value or "").strip()
        if value:
            names.append(value)
    return list(dict.fromkeys(names))


def read_domain(sheet) -> str:
    row, _ = settings.DRUG_NAME_CELL
    return str(sheet.cell(row, settings.DOMAIN_COLUMN).value or "").strip()


def read_sections(sheet) -> list:
    sections = []
    for row in range(settings.SECTION_START_ROW, sheet.max_row + 1):
        value = str(sheet.cell(row, settings.SECTION_COLUMN).value or "").strip()
        if value:
            sections.append(value)
    return list(dict.fromkeys(sections))


def read_drug_table(path: Path) -> list:
    workbook = openpyxl.load_workbook(path, data_only=True)
    drugs = []
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        row, column = settings.DRUG_NAME_CELL
        drug = str(sheet.cell(row, column).value or "").strip()
        if not drug:
            continue
        sections = read_sections(sheet)
        dimensions = [name for name in DRUG_DIMENSIONS if name in sections]
        drugs.append({
            "sheet": sheet_name,
            "drug": drug,
            "domain": read_domain(sheet),
            "competitors": [name for name in read_competitors(sheet) if name != drug],
            "sections": sections,
            "dimensions": dimensions or list(DRUG_DIMENSIONS),
        })
    return drugs


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_of(node) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def collect_section(section, level: int, lines: list) -> None:
    title = text_of(section.find("./title"))
    if title:
        lines.append(f"{'#' * level} {title}")
    for child in section:
        tag = local_tag(child.tag)
        if tag in SKIP_TAGS or tag == "title":
            continue
        if tag == "sec":
            collect_section(child, level + 1, lines)
        elif tag == "p":
            paragraph = text_of(child)
            if paragraph:
                lines.append(paragraph)


def extract_jats_article(article) -> dict:
    meta = article.find("./front/article-meta")
    ids = {}
    if meta is not None:
        for node in meta.findall("./article-id"):
            kind = node.attrib.get("pub-id-type", "")
            value = text_of(node)
            if kind and value:
                ids.setdefault(kind, value)

    title = text_of(meta.find("./title-group/article-title")) if meta is not None else ""

    abstracts = []
    if meta is not None:
        for abstract in meta.findall("./abstract"):
            paragraphs = [text_of(p) for p in abstract.findall(".//p")]
            text = " ".join(part for part in paragraphs if part) or text_of(abstract)
            if text:
                abstracts.append(text)

    lines = []
    body = article.find("./body")
    if body is not None:
        for child in body:
            tag = local_tag(child.tag)
            if tag in SKIP_TAGS:
                continue
            if tag == "sec":
                collect_section(child, 1, lines)
            elif tag == "p":
                paragraph = text_of(child)
                if paragraph:
                    lines.append(paragraph)

    return {
        "pmcid": ids.get("pmcid", ""),
        "doi": ids.get("doi", ""),
        "title": title,
        "abstract": "\n\n".join(abstracts),
        "full_text": "\n\n".join(lines),
    }


def parse_jats_articles(xml_text: str) -> dict:
    articles = {}
    for article in ET.fromstring(xml_text).iter("article"):
        info = extract_jats_article(article)
        key = info["pmcid"].upper()
        if key:
            articles[key] = info
    return articles


def fetch_europe_pmc_fulltext(pmcid: str) -> dict:
    if settings.FULLTEXT_PAUSE_SECONDS:
        time.sleep(settings.FULLTEXT_PAUSE_SECONDS)
    _, text = call_api(
        settings.EUROPE_PMC_FULLTEXT_URL.format(pmcid=pmcid),
        parser="text",
        timeout=settings.FULLTEXT_TIMEOUT,
        retry_times=settings.FULLTEXT_RETRY_TIMES,
        retry_wait=settings.FULLTEXT_RETRY_WAIT,
        validate=lambda value: "<article" in value,
    )
    for article in ET.fromstring(text).iter("article"):
        return extract_jats_article(article)
    return {}


def europe_pmc_item(rank: int, item: dict, unit: dict) -> dict:
    source_code = str(item.get("source") or "MED")
    identifier = str(item.get("id") or "")
    pmcid = str(item.get("pmcid") or "")
    abstract = str(item.get("abstractText") or "")


    article = {}
    if (
        pmcid
        and str(item.get("isOpenAccess") or "").upper() == "Y"
        and (rank <= settings.FULLTEXT_TOP_N or not abstract)
    ):
        try:
            article = fetch_europe_pmc_fulltext(pmcid)
        except Exception:
            article = {}
    full_text = article.get("full_text") or ""
    title = str(item.get("title") or article.get("title") or "")

    return make_result(
        rank=rank,
        title=title,
        content="\n\n".join(part for part in (abstract, full_text) if part),
        url=(
            f"https://europepmc.org/article/{source_code}/{identifier}"
            if identifier
            else ""
        ),
        doi=item.get("doi") or article.get("doi"),
        content_type=content_type_of(abstract, full_text),
        abstract_text=abstract,
        groups=unit["groups"],
        match_scope="title+abstract",
    )


def verify_europe_pmc(unit: dict) -> dict:
    url = settings.EUROPE_PMC_URL
    request = {"url": url, "method": "GET", "params": {}}

    local = with_keyword_groups(unit, Europe_PMC_query.keyword_groups(unit["dimension"]))
    try:
        params = Europe_PMC_query.build_params(
            Europe_PMC_query.build_drug_query(unit["name"], unit["dimension"]),
            sort=settings.EUROPE_PMC_SORT,
            page_size=settings.TOP_N,
        )
        request["params"] = params

        status, payload = call_api(
            url,
            params,
            validate=lambda data: "hitCount" in data,
            retry_times=settings.EUROPE_PMC_RETRY_TIMES,
            retry_wait=settings.EUROPE_PMC_RETRY_WAIT,
        )
        items = payload.get("resultList", {}).get("result", [])[: settings.TOP_N]
        results = [
            europe_pmc_item(rank, item, local) for rank, item in enumerate(items, start=1)
        ]
        return build_record(
            local, "Europe_PMC", request, status, to_int(payload.get("hitCount")), results
        )
    except Exception as exc:
        return build_record(local, "Europe_PMC", request, None, 0, [], error=str(exc))


def ncbi_params(extra: dict) -> dict:
    params = {"db": "pmc", "tool": settings.NCBI_TOOL}
    if settings.NCBI_EMAIL:
        params["email"] = settings.NCBI_EMAIL
    params.update(extra)
    return params


def fetch_pmc_summaries(ids: list) -> dict:
    _, payload = call_api(
        settings.PMC_SUMMARY_URL,
        ncbi_params({"id": ",".join(ids), "retmode": "json", "version": "2.0"}),
        method="post",
    )
    raw = payload.get("result", {})
    summaries = {}
    for uid in ids:
        item = raw.get(str(uid))
        if not isinstance(item, dict):
            continue
        doi = item.get("doi")
        article_ids = item.get("articleids", [])
        if not doi and isinstance(article_ids, list):
            for value in article_ids:
                if (
                    isinstance(value, dict)
                    and str(value.get("idtype", "")).lower() == "doi"
                ):
                    doi = value.get("value")
                    break
        summaries[str(uid)] = {
            "title": str(item.get("title") or ""),
            "pmcid": str(item.get("pmcid") or f"PMC{uid}"),
            "doi": doi,
        }
    return summaries


def fetch_pmc_articles(ids: list) -> dict:
    _, text = call_api(
        settings.PMC_FETCH_URL,
        ncbi_params({"id": ",".join(ids), "retmode": "xml"}),
        method="post",
        parser="text",
        timeout=settings.PMC_BATCH_TIMEOUT,
    )
    return parse_jats_articles(text)


def pmc_items(ids: list, unit: dict) -> list:
    summaries = fetch_pmc_summaries(ids)
    articles = fetch_pmc_articles(ids)
    results = []
    for rank, uid in enumerate(ids, start=1):
        item = summaries.get(str(uid), {})
        pmcid = item.get("pmcid") or f"PMC{uid}"
        article = articles.get(pmcid.upper(), {})
        abstract = article.get("abstract") or ""
        full_text = article.get("full_text") or ""
        title = article.get("title") or item.get("title", "")

        results.append(
            make_result(
                rank=rank,
                title=title,
                content="\n\n".join(part for part in (abstract, full_text) if part),
                url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                doi=article.get("doi") or item.get("doi"),
                content_type=content_type_of(abstract, full_text),
                abstract_text=abstract,
                groups=unit["groups"],
                match_scope="title+abstract",
            )
        )
    return results


def verify_pmc(unit: dict) -> dict:
    url = settings.PMC_URL
    request = {"url": url, "method": "POST (form)", "params": {}}

    local = with_keyword_groups(unit, PMC_query.keyword_groups(unit["dimension"]))
    try:
        params = ncbi_params(
            {
                "term": PMC_query.build_drug_query(unit["name"], unit["dimension"]),
                "retmax": settings.TOP_N,
                "retmode": "json",
                "sort": "relevance",
            }
        )
        request["params"] = params

        status, payload = call_api(
            url, params, method="post", validate=lambda data: "esearchresult" in data
        )
        search = payload.get("esearchresult", {})
        ids = [str(value) for value in search.get("idlist", [])][: settings.TOP_N]
        results = pmc_items(ids, local) if ids else []
        return build_record(local, "PMC", request, status, to_int(search.get("count")), results)
    except Exception as exc:
        return build_record(local, "PMC", request, None, 0, [], error=str(exc))


def clinicaltrials_sponsors(protocol: dict) -> tuple:
    module = protocol.get("sponsorCollaboratorsModule") or {}
    sponsor = str((module.get("leadSponsor") or {}).get("name") or "").strip()
    collaborators = []
    for item in module.get("collaborators") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            collaborators.append(name)
    return sponsor, collaborators


def build_clinicaltrials_content(protocol: dict) -> str:
    lines = []

    description = protocol.get("descriptionModule") or {}
    if description.get("briefSummary"):
        lines.append("# Brief summary")
        lines.append(str(description["briefSummary"]).strip())
    if description.get("detailedDescription"):
        lines.append("# Detailed description")
        lines.append(str(description["detailedDescription"]).strip())

    conditions = (protocol.get("conditionsModule") or {}).get("conditions") or []
    if conditions:
        lines.append("# Indications")
        lines.append(", ".join(str(value) for value in conditions))

    sponsor, collaborators = clinicaltrials_sponsors(protocol)
    if sponsor or collaborators:
        lines.append("# Sponsor and collaborators")
        if sponsor:
            lines.append(f"- Sponsor: {sponsor}")
        for name in collaborators:
            lines.append(f"- Collaborator: {name}")

    design = protocol.get("designModule") or {}
    design_lines = []
    phases = design.get("phases") or []
    if phases:
        design_lines.append("Trial phases: " + ", ".join(str(value) for value in phases))
    enrollment = design.get("enrollmentInfo") or {}
    if enrollment.get("count"):
        design_lines.append(f"Planned enrollment: {enrollment['count']}")
    if design_lines:
        lines.append("# Trial design")
        lines.extend(design_lines)

    interventions = (
        protocol.get("armsInterventionsModule") or {}
    ).get("interventions") or []
    if interventions:
        lines.append("# Interventions")
        for item in interventions:
            name = str(item.get("name") or "")
            kind = str(item.get("type") or "")
            text = f"{name}({kind})" if kind else name
            detail = str(item.get("description") or "").strip()
            lines.append(f"- {text}: {detail}" if detail else f"- {text}")

    outcomes = protocol.get("outcomesModule") or {}
    for key, label in (
        ("primaryOutcomes", "primary outcome measures"),
        ("secondaryOutcomes", "secondary outcome measures"),
    ):
        items = outcomes.get(key) or []
        if not items:
            continue
        lines.append(f"# {label}")
        for item in items:
            measure = str(item.get("measure") or "")
            detail = str(item.get("description") or "").strip()
            lines.append(f"- {measure}: {detail}" if detail else f"- {measure}")

    criteria = str(
        (protocol.get("eligibilityModule") or {}).get("eligibilityCriteria") or ""
    ).strip()
    if criteria:
        lines.append("# Eligibility criteria")
        lines.append(criteria)

    references = (protocol.get("referencesModule") or {}).get("references") or []
    if references:
        lines.append("# Related literature")
        for item in references:
            citation = str(item.get("citation") or "").strip()
            pmid = str(item.get("pmid") or "")
            lines.append(f"- {citation}(PMID: {pmid})" if pmid else f"- {citation}")

    return "\n\n".join(lines)


def verify_clinicaltrials(unit: dict) -> dict:
    url = settings.CLINICALTRIALS_URL
    request = {"url": url, "method": "GET", "params": {}}

    local = with_keyword_groups(unit, ClinicalTrials_query.keyword_groups(unit["dimension"]))
    try:
        params = ClinicalTrials_query.build_params(unit["name"], unit["dimension"])
        params["pageSize"] = settings.TOP_N
        request["params"] = params
        status, payload = call_api(url, params, validate=lambda data: "studies" in data)
        results = []
        for rank, study in enumerate(payload.get("studies", [])[: settings.TOP_N], start=1):
            protocol = study.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            nct_id = str(ident.get("nctId") or "")
            title = str(ident.get("briefTitle") or "")
            brief = str((protocol.get("descriptionModule") or {}).get("briefSummary") or "")
            sponsor, collaborators = clinicaltrials_sponsors(protocol)
            results.append(
                make_result(
                    rank=rank,
                    title=title,
                    content=build_clinicaltrials_content(protocol),
                    url=f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
                    doi=None,
                    content_type="full_record",
                    abstract_text=brief,
                    groups=local["groups"],
                    match_scope="title+brief summary",
                    extra={"sponsor": sponsor, "collaborator": collaborators},
                )
            )
        return build_record(
            local, "ClinicalTrials", request, status, to_int(payload.get("totalCount")), results
        )
    except Exception as exc:
        return build_record(local, "ClinicalTrials", request, None, 0, [], error=str(exc))


def parse_arxiv_feed(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("a:entry", ARXIV_NS):
        doi_node = entry.find("arxiv:doi", ARXIV_NS)
        entries.append(
            {
                "title": text_of(entry.find("a:title", ARXIV_NS)),
                "abstract": text_of(entry.find("a:summary", ARXIV_NS)),
                "url": text_of(entry.find("a:id", ARXIV_NS)),
                "doi": text_of(doi_node) if doi_node is not None else None,
                "published": text_of(entry.find("a:published", ARXIV_NS)),
            }
        )
    return {"total": to_int(text_of(root.find("os:totalResults", ARXIV_NS))), "entries": entries}


def verify_arxiv(unit: dict) -> dict:
    url = settings.ARXIV_URL
    request = {"url": url, "method": "GET", "params": {}}

    local = with_keyword_groups(unit, arxiv_query.keyword_groups(unit["dimension"]))
    try:
        params = {
            "search_query": arxiv_query.build_drug_query(unit["name"], unit["dimension"]),
            "start": 0,
            "max_results": settings.TOP_N,
            "sortBy": "relevance",
        }
        request["params"] = params
        status, text = call_api(
            url, params, parser="text", timeout=settings.ARCHIVE_TIMEOUT
        )
        feed = parse_arxiv_feed(text)
        results = []
        for rank, entry in enumerate(feed["entries"][: settings.TOP_N], start=1):
            results.append(
                make_result(
                    rank=rank,
                    title=entry["title"],
                    content=entry["abstract"],
                    url=entry["url"],
                    doi=entry["doi"],
                    content_type="abstract_only",
                    abstract_text=entry["abstract"],
                    groups=local["groups"],
                    match_scope="title+abstract",
                )
            )
        return build_record(local, "arxiv", request, status, feed["total"], results)
    except Exception as exc:
        return build_record(local, "arxiv", request, None, 0, [], error=str(exc))


def tavily_item(rank: int, item: dict, unit: dict) -> dict:
    raw = str(item.get("raw_content") or "")
    snippet = str(item.get("content") or "")
    return make_result(
        rank=rank,
        title=str(item.get("title") or ""),
        content=raw or snippet,
        url=str(item.get("url") or ""),
        doi=None,
        content_type="page_text" if raw else "page_snippet",
        abstract_text=snippet,
        groups=unit["groups"],
        match_scope="title+web snippet",
    )


def verify_tavily(unit: dict) -> dict:
    url = settings.TAVILY_URL
    request = {"url": url, "method": "POST(JSON)", "params": {}}

    local = with_keyword_groups(unit, tavily_query.keyword_groups(unit["dimension"]))
    try:
        payload = tavily_query.build_payload(
            unit["name"], unit["dimension"], domain=unit.get("domain", "")
        )
        payload["api_key"] = settings.TAVILY_API_KEY
        payload["max_results"] = settings.TOP_N

        request["params"] = {key: value for key, value in payload.items() if key != "api_key"}
        status, data = call_api(
            url, method="post", payload=payload, validate=lambda value: "results" in value
        )
        items = data.get("results", [])[: settings.TOP_N]
        results = [tavily_item(rank, item, local) for rank, item in enumerate(items, start=1)]

        return build_record(local, "tavily", request, status, len(items), results)
    except Exception as exc:
        return build_record(local, "tavily", request, None, 0, [], error=str(exc))


def es_endpoint() -> str:
    return f"{settings.ES_URL.rstrip('/')}/{settings.ES_INDEX}/_search"


def es_item(rank: int, hit: dict, unit: dict) -> dict:
    src = hit.get("_source") or {}
    title = str(src.get("article_title_en") or "")
    abstract = str(src.get("abstract_en") or "")
    doi = str(src.get("doi") or "")
    journal = str(src.get("journal_title") or "")
    if src.get("journal_iso_abbr"):
        journal = f"{journal}({src['journal_iso_abbr']})"
    types = ", ".join(str(value) for value in (src.get("article_type") or []))
    meta = [
        f"Database ID: {src.get('id') or hit.get('_id') or ''}",
        f"Journal: {journal}" if journal else "",
        f"Year: {src.get('publication_year') or ''}",
        f"Impact factor: {src.get('impact_factor')}" if src.get("impact_factor") is not None else "",
        f"JCR quartile: {src.get('jcr_quartile') or ''}",
        f"Article type: {types}" if types else "",
        f"DOI: {doi}" if doi else "",
    ]
    content = "# Document metadata\n" + "; ".join(part for part in meta if part)
    if abstract:
        content += f"\n\n# Abstract\n{abstract}"
    result = make_result(
        rank=rank,
        title=title,
        content=content,
        url=f"https://doi.org/{doi}" if doi else "",
        doi=doi or None,
        content_type=content_type_of(abstract, ""),
        abstract_text=abstract,
        groups=unit["groups"],
        match_scope="title+abstract",
    )
    score = hit.get("_score")
    if isinstance(score, (int, float)):
        result["relevance_score"] = round(float(score), 4)
    return result


def verify_es(unit: dict) -> dict:
    url = es_endpoint()
    request = {"url": url, "method": "POST(JSON)", "params": {}}

    local = with_keyword_groups(unit, ES_query.keyword_groups(unit["dimension"]))
    try:
        payload = ES_query.build_payload(unit["name"], unit["dimension"], size=settings.TOP_N)
        request["params"] = {
            "index": settings.ES_INDEX,
            "search fields": list(settings.ES_SEARCH_FIELDS),
            "returned fields": list(settings.ES_SOURCE_FIELDS),

            "narrow_keywords": ES_query.first_group(unit["dimension"], local["groups"]),
            "query": payload["query"]["query_string"]["query"],
            "size": settings.TOP_N,
        }
        status, data = call_api(
            url,
            method="post",
            payload=payload,
            auth=(settings.ES_USER, settings.ES_PASSWORD),
            use_proxy=settings.ES_USE_PROXY,
            validate=lambda value: "hits" in value,
        )
        hits_block = data.get("hits") or {}
        total = to_int((hits_block.get("total") or {}).get("value"))
        hits = (hits_block.get("hits") or [])[: settings.TOP_N]
        results = [es_item(rank, hit, local) for rank, hit in enumerate(hits, start=1)]
        return build_record(local, "ES", request, status, total, results)
    except Exception as exc:
        return build_record(local, "ES", request, None, 0, [], error=str(exc))


FETCHERS = {
    "Europe_PMC": verify_europe_pmc,
    "PMC": verify_pmc,
    "ES": verify_es,
}


LANDSCAPE_DIMENSION = "Competitive Landscape"


UNSAFE_NAME_CHARS = r'[\\/:*?"<>|]+'


def safe_name(name: str) -> str:
    cleaned = re.sub(UNSAFE_NAME_CHARS, "_", str(name or "").strip())
    return cleaned or "unnamed"


def object_dir(source_root: str, drug: str, competitor=None, root=None) -> Path:
    directory = Path(root or BASE_DIR) / source_root / safe_name(drug)
    if competitor:
        directory = directory / settings.COMPETITOR_DIR_NAME / safe_name(competitor)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def interface_output_path(source: str, drug: str, name: str, dimension: str, competitor=None, root=None) -> Path:
    directory = object_dir(f"{source}/output", drug, competitor, root)
    return directory / f"{safe_name(competitor or name)}_{dimension}.json"


def summary_output_path(drug: str, name: str, dimension: str, competitor=None, root=None) -> Path:
    directory = object_dir(
        f"{settings.ALL_RESULT_DIR}/{settings.ALL_RESULT_OUTPUT_DIR}", drug, competitor, root
    )
    return directory / f"{safe_name(competitor or name)}_{dimension}.json"


def build_unit(info: dict, dimension: str, name: str, is_competitor: bool) -> dict:
    return {
        "target": f"{name}_{dimension}",
        "drug": name,
        "name": name,
        "object": name,
        "object_type": "drug",
        "parent_drug": info["drug"],
        "is_competitor": is_competitor,
        "domain": info.get("domain", ""),
        "dimension": dimension,
    }


def with_keyword_groups(unit: dict, groups: list) -> dict:
    return {**unit, "groups": groups, "keywords": [group["raw"] for group in groups]}


def run_unit(unit: dict, sources: list, root: Path = None) -> tuple:
    competitor = unit["name"] if unit["is_competitor"] else None
    records, entries = [], []
    for source in sources:
        started = time.time()
        try:
            record = FETCHERS[source](unit)
        except Exception as exc:
            record = build_record(
                unit, source, {"url": "", "params": {}}, None, 0, [], error=f"unexpected error: {exc}"
            )
        record["object"] = unit["name"]
        record["parent_drug"] = unit["parent_drug"]
        record["is_competitor"] = unit["is_competitor"]
        save_json(
            interface_output_path(
                source, unit["parent_drug"], unit["name"], unit["dimension"], competitor, root
            ),
            record,
        )
        records.append(record)
        entries.append({
            "object": unit["name"],
            "is_competitor": unit["is_competitor"],
            "dimension": unit["dimension"],
            "source": source,
            "ok": record["ok"],
            "status_code": record["status_code"],
            "returned_results": record["returned_results"],
            "seconds": round(time.time() - started, 1),
            "error": record["error"],
        })
    return records, entries


def build_landscape(info: dict, objects: list, sources: list) -> dict:
    rows = []
    dimensions = []
    for obj in objects:
        metrics = {}
        for record in obj["records"]:
            if record["dimension"] not in dimensions:
                dimensions.append(record["dimension"])
            metrics.setdefault(record["dimension"], {})[record["source"]] = {
                "ok": record["ok"],
                "total_results": record["total_results"],
                "returned_results": record["returned_results"],
                "full_text_count": record["metrics"]["full_text_count"],
                "avg_match_ratio": record["metrics"]["avg_match_ratio"],
                "keyword_coverage": record["metrics"]["keyword_coverage"],
                "error": record["error"],
            }
        rows.append({"object": obj["name"], "is_competitor": obj["is_competitor"], "metrics": metrics})
    return {
        "drug": info["drug"],
        "domain": info.get("domain", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": list(sources),
        "dimensions": dimensions,
        "objects": rows,
    }


def run_table(sheets=None, dimensions=None, sources=None, competitors=None, root=None, table=None) -> list:
    table = table or (BASE_DIR / settings.DRUG_TABLE)
    explicit_sources = sources is not None
    sources = list(sources or configured_sources())
    outputs = []
    for info in read_drug_table(table):
        if sheets and info["sheet"] not in sheets:
            continue
        selected = [name for name in info["dimensions"] if not dimensions or name in dimensions]
        if not selected:
            continue
        competitor_names = list(competitors) if competitors is not None else list(info["competitors"])
        notes = []
        if competitors is None and not competitor_names:
            notes.append("No competitor list provided (column B of the sheet is empty); only the main drug was retrieved in this run")
        if not explicit_sources and "tavily" not in sources:
            notes.append("tavily has no API key configured (settings.TAVILY_API_KEY or the environment variable); this interface was skipped in this run")
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        objects, entries = [], []
        for name, is_competitor in [(info["drug"], False)] + [(item, True) for item in competitor_names]:
            records = []
            for dimension in selected:
                unit = build_unit(info, dimension, name, is_competitor)
                unit_records, unit_entries = run_unit(unit, sources, root)
                records.extend(unit_records)
                entries.extend(unit_entries)
                save_json(
                    summary_output_path(
                        info["drug"], name, dimension, name if is_competitor else None, root
                    ),
                    build_all_result(unit_records),
                )
            objects.append({"name": name, "is_competitor": is_competitor, "records": records})

        save_json(
            summary_output_path(info["drug"], info["drug"], LANDSCAPE_DIMENSION, None, root),
            build_landscape(info, objects, sources),
        )

        log_path = object_dir(
            f"{settings.ALL_RESULT_DIR}/{settings.ALL_RESULT_OUTPUT_DIR}", info["drug"], None, root
        ) / settings.RUN_LOG_NAME
        merged_units, first_started = {}, started_at
        if log_path.exists():
            try:
                previous = json.loads(log_path.read_text(encoding="utf-8"))
                first_started = min(previous.get("started_at") or started_at, started_at)
                merged_units = {
                    (unit["object"], unit["dimension"], unit["source"]): unit
                    for unit in previous.get("units", [])
                }
            except Exception:
                merged_units = {}
        for entry in entries:
            merged_units[(entry["object"], entry["dimension"], entry["source"])] = entry
        all_units = list(merged_units.values())

        log_dimensions = list(dict.fromkeys(unit["dimension"] for unit in all_units)) or selected
        save_json(
            log_path,
            {
                "drug": info["drug"],
                "sheet": info["sheet"],
                "sections": info.get("sections", []),
                "started_at": first_started,
                "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sources": sources,
                "dimensions": log_dimensions,
                "competitors": competitor_names,
                "notes": notes,
                "units": all_units,
                "summary": {
                    "total": len(all_units),
                    "ok": sum(1 for entry in all_units if entry["ok"]),
                    "failed": sum(1 for entry in all_units if not entry["ok"]),
                },
            },
        )
        outputs.append({"drug": info["drug"], "objects": [obj["name"] for obj in objects]})
    return outputs


def main() -> None:
    argv = sys.argv[1:]
    table_name = settings.DRUG_TABLE
    if "--table" in argv:
        index = argv.index("--table")
        if index + 1 >= len(argv):
            raise SystemExit('--table needs a table name, e.g. --table "unapproved drugs.xlsx"')
        table_name = argv[index + 1]
        argv = argv[:index] + argv[index + 2:]
    sources = None
    if "--sources" in argv:
        index = argv.index("--sources")
        if index + 1 >= len(argv):
            raise SystemExit("--sources needs interface names, e.g. --sources Europe_PMC,PMC")
        sources = [item.strip() for item in argv[index + 1].split(",") if item.strip()]
        argv = argv[:index] + argv[index + 2:]
    table = BASE_DIR / table_name
    if not table.exists():
        choices = ", ".join('"%s"' % name for name in settings.DRUG_TABLES)
        raise SystemExit(f"Table not found: {table}(choices: {choices})")
    if argv:
        known = {info["sheet"] for info in read_drug_table(table)}
        unknown = [name for name in argv if name not in known]
        if unknown:
            raise SystemExit(f"{table_name} has no such sheet: {', '.join(unknown)}")
    run_table(sheets=argv or None, sources=sources, table=table)


if __name__ == "__main__":
    main()
