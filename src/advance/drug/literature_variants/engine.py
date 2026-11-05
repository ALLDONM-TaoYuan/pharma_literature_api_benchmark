"""Shared query planning, retrieval, provenance, ranking and full-text hydration."""
from __future__ import annotations

import copy
import hashlib
import html
import json
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                          if (p / "src" / "__init__.py").exists())))
from src.paths import advance_data  # noqa: E402

import main as project  # noqa: E402
from config import Europe_PMC_query, PMC_query, drug_forms, quoted_phrase, settings  # noqa: E402

DATA = advance_data("drug")
DIMENSIONS = ("Basic Information", "Clinical Studies", "Non-Clinical Studies")
TABLES = ("approved drugs.xlsx", "unapproved drugs.xlsx")
BASE_MODULES = {"Europe_PMC": Europe_PMC_query, "PMC": PMC_query}


def load_priors(path=None):
    path = Path(path) if path else Path(__file__).with_name("legacy_priors.json")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def unique_words(words):
    return list(dict.fromkeys(str(word).strip() for word in words if str(word).strip()))


def aliases_of(entity, aliases):
    return unique_words(aliases.get(entity) or drug_forms(entity))


def keyword_groups(backend, dimension, keywords=None):
    source = keywords if keywords is not None else BASE_MODULES[backend].KEYWORDS
    if dimension not in DIMENSIONS:
        raise ValueError("Unknown dimension: " + str(dimension))
    return [{"raw": " OR ".join(words), "words": list(words)}
            for words in source.get(dimension, [])]


def clause(backend, words, force_quotes=True):
    words = unique_words(words)
    if not words:
        raise ValueError("Empty query clause")
    suffix = "[AllFields]" if backend == "PMC" else ""
    def term(word):
        return quoted_phrase(word) if force_quotes or re.search(r"[^0-9A-Za-z]", word) else word
    return "(" + " OR ".join(term(word) + suffix for word in words) + ")"


def build_query_text(backend, entity, dimension, anchor=None, info_group=None,
                     with_narrow=True, info_mode="AND", keywords=None):
    if backend not in BASE_MODULES:
        raise ValueError("Unknown backend: " + backend)
    if info_mode not in ("AND", "OR"):
        raise ValueError("info_mode must be AND or OR")
    names = drug_forms(entity) if anchor is None else ([anchor] if isinstance(anchor, str) else anchor)
    names = unique_words(names)
    if not names:
        raise ValueError("An entity anchor is required")
    groups = keyword_groups(backend, dimension, keywords)
    body = []
    for group in groups:
        words = group["words"]
        body.extend(words[:settings.PMC_WORDS_LIMIT] if backend == "PMC" else words)
    info_words = unique_words(info_group[1]) if info_group else []
    parts = [clause(backend, names + info_words if info_mode == "OR" else names)]
    if with_narrow and body:
        parts.append(clause(backend, body, force_quotes=False))
    if info_words and info_mode == "AND":
        parts.append(clause(backend, info_words, force_quotes=False))
    return " AND ".join(parts)


def build_rounds(backend, variant, entity, dimension, aliases, info_terms,
                 info_mode="AND", narrow_in_all_rounds=False, keywords=None):
    if variant not in (1, 2, 3, 4):
        raise ValueError("variant must be 1, 2, 3 or 4")
    anchors = aliases_of(entity, aliases) if variant in (2, 4) else [None]
    groups = [(label, words) for label, words in info_terms.get(entity, {}).items()
              if not label.startswith("_") and unique_words(words)] if variant in (3, 4) else []
    rounds, seen = [], set()
    for anchor in anchors:
        for info_group, narrow in [(None, True)] + [(g, narrow_in_all_rounds) for g in groups]:
            query = (BASE_MODULES[backend].build_drug_query(entity, dimension)
                     if anchor is None and info_group is None and
                     (keywords is None or keywords == BASE_MODULES[backend].KEYWORDS) else
                     build_query_text(backend, entity, dimension, anchor, info_group,
                                      narrow, info_mode, keywords))
            if query in seen:
                continue
            seen.add(query)
            rounds.append({"round": len(rounds) + 1, "query": query,
                           "anchor": anchor if anchor is not None else drug_forms(entity),
                           "info_group": info_group[0] if info_group else "",
                           "with_narrow": narrow})
    return rounds


def request_spec(backend, query, size):
    if size < 1 or size > 1000:
        raise ValueError("per-round size must be between 1 and 1000")
    if backend == "Europe_PMC":
        return {"url": settings.EUROPE_PMC_URL, "method": "GET",
                "params": Europe_PMC_query.build_params(query, settings.EUROPE_PMC_SORT, size)}
    return {"url": settings.PMC_URL, "method": "POST",
            "params": project.ncbi_params({"term": query, "retmax": size,
                                            "retmode": "json", "sort": "relevance"})}


class SearchClient:
    def __init__(self, retry_times=None, timeout=None):
        self.cache = {}
        self.last_request = 0.0
        self.retry_times = retry_times
        self.timeout = timeout

    def search(self, backend, spec):
        key = (backend, json.dumps(spec, sort_keys=True))
        if key in self.cache:
            return copy.deepcopy(self.cache[key]), True
        delay = (0.4 if backend == "PMC" else 0.2) - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        self.last_request = time.monotonic()
        kwargs = {"method": spec["method"].lower()}
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        if self.retry_times is not None:
            kwargs["retry_times"] = self.retry_times
        if backend == "Europe_PMC":
            kwargs.setdefault("retry_times", settings.EUROPE_PMC_RETRY_TIMES)
            kwargs["retry_wait"] = settings.EUROPE_PMC_RETRY_WAIT
            kwargs["validate"] = lambda data: isinstance(data, dict) and "hitCount" in data
        else:
            kwargs["validate"] = lambda data: (isinstance(data, dict) and
                "esearchresult" in data and "ERROR" not in data and
                "ERROR" not in data.get("esearchresult", {}) and
                "count" in data.get("esearchresult", {}) and
                not data.get("esearchresult", {}).get("errorlist", {}).get("fieldsnotfound"))
        status, data = project.call_api(spec["url"], spec["params"], **kwargs)
        if backend == "Europe_PMC":
            result = {"status": status, "total": project.to_int(data["hitCount"]),
                      "items": data.get("resultList", {}).get("result", [])[:spec["params"]["pageSize"]]}
        else:
            search = data["esearchresult"]
            result = {"status": status, "total": project.to_int(search.get("count")),
                      "items": [{"pmcid": "PMC" + str(uid).removeprefix("PMC"), "uid": str(uid)}
                                for uid in search.get("idlist", [])[:spec["params"]["retmax"]]],
                      "query_translation": search.get("querytranslation", ""),
                      "warnings": search.get("warninglist", {}),
                      "query_diagnostics": search.get("errorlist", {})}
        self.cache[key] = copy.deepcopy(result)
        return result, False


def identity_keys(item):
    keys = []
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "",
                 str(item.get("doi") or "").strip(), flags=re.I).lower().rstrip(".")
    if doi:
        keys.append("doi:" + doi)
    pmcid = str(item.get("pmcid") or "").strip().upper()
    if pmcid:
        keys.append("pmc:" + pmcid)
    identifier = str(item.get("id") or "").strip()
    if identifier:
        keys.append("source:" + str(item.get("source") or "MED").upper() + ":" + identifier)

    if not keys:
        title = re.sub(r"[^\w]+", "", html.unescape(str(item.get("title") or "")).casefold())
        if title:
            keys.append("title:" + title)
    if not keys:
        raise ValueError("Search result has no usable identifier or title")
    return keys


def merge_candidates(rounds):
    parents, nodes, identifiers = [], [], {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for rd in rounds:
        for rank, item in enumerate(rd.get("items", []), 1):
            keys = identity_keys(item)
            index = len(nodes)
            parents.append(index)
            nodes.append({"item": item, "round": rd["round"], "rank": rank})
            for key in keys:
                if key in identifiers:
                    parents[find(index)] = find(identifiers[key])
                else:
                    identifiers[key] = index
    groups = {}
    for index, node in enumerate(nodes):
        groups.setdefault(find(index), []).append(node)
    merged = []
    for group in groups.values():
        item = copy.deepcopy(group[0]["item"])
        ranks = {}
        for node in group:
            ranks[node["round"]] = min(ranks.get(node["round"], node["rank"]), node["rank"])
            for key, value in node["item"].items():
                if value and not item.get(key):
                    item[key] = value
        provenance = [{"round": number, "rank": rank} for number, rank in sorted(ranks.items())]
        merged.append({"item": item, "retrieved_by": provenance,
                       "fusion_score": sum(1.0 / (60 + rank) for rank in ranks.values()),
                       "first_seen": (group[0]["round"], group[0]["rank"])})
    return sorted(merged, key=lambda c: (-c["fusion_score"], c["first_seen"]))


def fulltext_targets(candidates):
    targets = []
    for rank, candidate in enumerate(candidates, 1):
        raw = candidate.get("item") or {}
        pmcid = str(raw.get("pmcid") or "")
        if not pmcid or rank > settings.FULLTEXT_TOP_N:
            continue
        if str(raw.get("isOpenAccess") or "").upper() != "Y":
            continue
        if pmcid not in targets:
            targets.append(pmcid)
    return targets


def prefetch_fulltext(candidates):
    targets = fulltext_targets(candidates)
    if not targets:
        return {}, 0, []

    def one(pmcid):
        try:
            return pmcid, project.fetch_europe_pmc_fulltext(pmcid)
        except Exception as exc:
            return pmcid, {"__error__": str(exc)}

    articles, failed = {}, []
    workers = max(1, int(getattr(settings, "FULLTEXT_WORKERS", 4)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pmcid, article in pool.map(one, targets):
            if "__error__" in article:
                failed.append({"pmcid": pmcid, "error": article["__error__"]})
            elif article:
                articles[pmcid] = article
    return articles, len(targets), failed


def hydrate(backend, candidates, unit, fulltext=True):
    results, errors = [], []
    if backend == "Europe_PMC":
        articles, attempted, failed = prefetch_fulltext(candidates) if fulltext else ({}, 0, [])
        for rank, candidate in enumerate(candidates, 1):
            raw = copy.deepcopy(candidate["item"])
            pmcid = str(raw.get("pmcid") or "")
            article = articles.get(pmcid) or {}
            abstract = str(raw.get("abstractText") or "")
            text = article.get("full_text") or ""
            source_code = str(raw.get("source") or "MED")
            identifier = str(raw.get("id") or "")

            result = project.make_result(
                rank=rank,
                title=str(raw.get("title") or article.get("title") or ""),
                content="\n\n".join(part for part in (abstract, text) if part),
                url=(f"https://europepmc.org/article/{source_code}/{identifier}" if identifier else ""),
                doi=raw.get("doi") or article.get("doi"),
                content_type=project.content_type_of(abstract, text),
                abstract_text=abstract,
                groups=unit["groups"],
                match_scope="title+abstract+full text" if text else "title+abstract")
            result.update({"pmcid": pmcid, "publication_year": raw.get("pubYear", ""),
                           "article_type": raw.get("pubTypeList", {}).get("pubType", []),
                           "database_id": identifier,
                           "database_source": source_code,
                           "is_open_access": str(raw.get("isOpenAccess") or "N").upper() == "Y",
                           "full_text_chars": len(text), "abstract_chars": len(abstract)})
            results.append(result)
    else:
        ids = [c["item"]["uid"] for c in candidates]
        summaries, articles = {}, {}
        if ids:
            try:
                summaries = project.fetch_pmc_summaries(ids)
            except Exception as exc:
                errors.append({"stage": "esummary", "error": str(exc)})

            try:
                time.sleep(0.4)
                articles = project.fetch_pmc_articles(ids)
            except Exception as exc:
                errors.append({"stage": "efetch", "error": str(exc)})
        for rank, candidate in enumerate(candidates, 1):
            raw = candidate["item"]
            summary = summaries.get(raw["uid"], {})
            article = articles.get(raw["pmcid"], {})
            abstract = article.get("abstract") or ""
            text = article.get("full_text") or "" if fulltext else ""
            results.append(project.make_result(
                rank=rank, title=article.get("title") or summary.get("title", ""),
                content="\n\n".join(p for p in (abstract, text) if p),
                url="https://pmc.ncbi.nlm.nih.gov/articles/" + raw["pmcid"] + "/",
                doi=article.get("doi") or summary.get("doi"),
                content_type=project.content_type_of(abstract, text), abstract_text=abstract,
                groups=unit["groups"], match_scope="title+abstract",
                extra={"pmcid": raw["pmcid"], "database_id": raw["uid"]}))
    for result, candidate in zip(results, candidates):
        result["retrieved_by"] = candidate["retrieved_by"]
        result["fusion_score"] = round(candidate["fusion_score"], 8)
    if backend == "Europe_PMC":
        full_chars = [r.get("full_text_chars", 0) for r in results if r.get("content_type") == "full_text"]
        abstract_chars = [r.get("abstract_chars", 0) for r in results if r.get("abstract_chars")]
        meta = {
            "enabled": bool(fulltext),
            "attempted": attempted,
            "retrieved": len(articles),
            "failed": len(failed),
            "failures": failed[:20],
            "selected": len(results),
            "full_text_count": len(full_chars),
            "abstract_only_count": sum(1 for r in results if r.get("content_type") == "abstract_only"),
            "metadata_only_count": sum(1 for r in results if r.get("content_type") == "metadata_only"),
            "coverage_of_selected": round(len(full_chars) / len(results), 4) if results else 0.0,
            "coverage_of_attempted": round(len(articles) / attempted, 4) if attempted else 0.0,
            "avg_full_text_chars": round(sum(full_chars) / len(full_chars)) if full_chars else 0,
            "avg_abstract_chars": round(sum(abstract_chars) / len(abstract_chars)) if abstract_chars else 0,
            "avg_content_chars": round(sum(r.get("content_length", 0) for r in results) / len(results)) if results else 0,
            "full_text_top_n": settings.FULLTEXT_TOP_N,
        }
    else:
        meta = {"enabled": bool(fulltext), "backend": backend,
                "full_text_count": sum(1 for r in results if r.get("content_type") == "full_text"),
                "selected": len(results),
                "coverage_of_selected": round(
                    sum(1 for r in results if r.get("content_type") == "full_text") / len(results), 4)
                if results else 0.0}
    return results, errors, meta


def retrieve(unit, backend, variant, aliases, info_terms, *, limit=20, per_round=20,
             info_mode="AND", narrow_in_all_rounds=False, keywords=None, client=None,
             fulltext=True, merge_order="rrf"):
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if merge_order not in ("rrf", "round"):
        raise ValueError("merge_order must be rrf or round")
    client = client or SearchClient()
    local = project.with_keyword_groups(unit, keyword_groups(backend, unit["dimension"], keywords))
    plan = build_rounds(backend, variant, unit["name"], unit["dimension"], aliases, info_terms,
                        info_mode, narrow_in_all_rounds, keywords)
    rounds = []
    for step in plan:
        rd = {**step, "request": request_spec(backend, step["query"], per_round)}
        try:
            response, cached = client.search(backend, rd["request"])
            rd.update(response, cached=cached, ok=True, error=None)
        except Exception as exc:
            rd.update(status=None, total=0, items=[], ok=False, cached=False, error=str(exc))
        rounds.append(rd)
    candidates = merge_candidates(rounds)
    if merge_order == "round":
        candidates.sort(key=lambda c: c["first_seen"])
    selected = candidates[:limit]
    results, hydration_errors, fulltext_meta = hydrate(backend, selected, local, fulltext)
    failures = [rd for rd in rounds if not rd["ok"]]
    source = backend if variant == 1 else backend + str(variant)
    audit = [{k: v for k, v in rd.items() if k != "items"} | {"fetched": len(rd["items"])} for rd in rounds]
    total = sum(rd["total"] for rd in rounds)
    error = f"{len(failures)}/{len(rounds)} search rounds failed" if failures else None
    if hydration_errors:
        error = (error + "; " if error else "") + "Some article detail requests failed"
    record = project.build_record(local, source, {"backend": backend, "rounds": audit},
                                  None if failures else 200, total, results, error)
    record.update({"variant": variant, "rounds": audit, "candidate_unique_count": len(candidates),
                   "search_hit_sum": total, "total_results_semantics": "overlapping_sum_of_round_hit_counts",
                   "partial_success": bool(results) and bool(error), "hydration_errors": hydration_errors,
                   "fulltext": fulltext_meta,
                   "selection": {"per_round": per_round, "final_limit": limit,
                                 "merge_order": merge_order, "rrf_k": 60 if merge_order == "rrf" else None},
                   "experiment": {"aliases_enabled": variant in (2, 4), "info_enabled": variant in (3, 4),
                                  "info_mode": info_mode, "narrow_in_all_rounds": narrow_in_all_rounds,
                                  "aliases": aliases_of(unit["name"], aliases) if variant in (2, 4) else [],
                                  "info_terms": info_terms.get(unit["name"], {}) if variant in (3, 4) else {},
                                  "prior_sha256": hashlib.sha256(json.dumps(
                                      {"aliases": aliases, "info_terms": info_terms}, sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()}})
    return record
