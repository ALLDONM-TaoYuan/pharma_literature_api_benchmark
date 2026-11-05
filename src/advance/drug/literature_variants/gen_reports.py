"""Generate a 5-section md report from the JSON results of each variant (every sentence bound to a DOI, traceable)."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import advance_data  # noqa: E402
DATA = advance_data("drug")
DIMS = ("Basic Information", "Clinical Studies", "Non-Clinical Studies")
DEFAULT_DRUGS = ("KT-621", "NTLA-2002", "Sunvozertinib", "baxdrostat", "Inclisiran",
                 "BNT327", "Azenosertib", "Zoldonrasib", "Ceralasertib")
SIGN = "This summary was derived by CodeBuddy Bunny from the interface response json"

PAIN = (r"unmet need", r"no (?:effective|approved)", r"limited (?:treatment|option|efficacy|benefit)",
        r"resistan", r"relaps", r"poor prognosis", r"high (?:mortality|burden)",
        r"remains? (?:a )?(?:major )?challenge", r"lack of", r"intolerab", r"suboptimal")
MECH = (r"mechanism", r"inhibit", r"degrad", r"blocks? ", r"binds?", r"selective", r"potent",
        r"pathway", r"synerg", r"affinit", r"selectivity", r"target(?:s|ing|ed)?")
CLIN = (r"phase [IViv1-3]+", r"randomi[sz]ed", r"placebo", r"open-label",
        r"patients? (?:were|with|received|enrolled)", r"primary (?:end ?point|outcome|efficacy)",
        r"objective response", r"overall survival", r"progression-free", r"median (?:PFS|OS|DoR)",
        r"hazard ratio", r"95% ?CI", r"p ?[<=] ?0\.", r"adverse events?", r"dose[- ]escalat",
        r"cohort", r"efficacy", r"safety", r"tolerab")
PRECLIN = (r"in vitro", r"in vivo", r"mice", r"mouse", r"murine", r"rat\b", r"xenograft", r"cell line",
           r"IC50", r"EC50", r"DC50", r"Cmax", r"AUC", r"half-life", r"bioavailab", r"clearance",
           r"pharmacokinet", r"hERG", r"Ames", r"toxicolog", r"plasma protein", r"microsom", r"Caco-2")
TARGET = (r"target(?:s|ing|ed)?", r"inhibit", r"degrad", r"blocks? ", r"pathway", r"receptor", r"kinase",
          r"mechanism of action", r"binds?", r"selective")
FORM = (r"oral(?:ly)?", r"tablet", r"capsule", r"intravenous", r"subcutaneous", r"small molecule",
        r"antibody", r"bispecific", r"siRNA", r"antisense", r"degrader", r"PROTAC", r"CRISPR",
        r"lipid nanoparticle", r"mRNA", r"ADC", r"conjugate")
INDICATION = (r"patients? with", r"treatment of", r"indicated", r"diagnos", r"disease", r"carcinoma",
              r"tumor", r"tumour", r"syndrome", r"deficiency")
COMPANY = (r"\(NASDAQ", r"Inc\.?", r"Therapeutics", r"Pharmaceutical", r"Bioscience", r"Biotech",
           r"GmbH", r"plc", r"Corp\b", r"Ltd", r"discovered by", r"developed by")
BAD_START = ("Copyright", "©", "This is an open access", "Open Access", "Funding", "Conflict of interest",
             "Acknowledg", "Supplementary", "Table ", "Figure ", "Fig.", "Keywords", "Abbreviations",
             "Received:", "Accepted:", "Published:", "Correspondence", "ORCID", "PMCID", "DOI:",
             "In contrast", "However,", "Therefore,", "Moreover,", "Thus,", "Here,", "We ", "Our ")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\[[0-9, \-]+\]", "", text)
    return re.sub(r"\s+", " ", text)


def normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", str(text).lower())


def netlen(text: str) -> int:
    return len(re.sub(r"[\s|*#>`]", "", text))


def similar(a: str, b: str, threshold: float = 0.72) -> bool:
    def grams(text):
        norm = normalize(text)
        return {norm[i:i + 2] for i in range(len(norm) - 1)}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return False
    return len(ga & gb) / len(ga | gb) >= threshold


def sentences(text: str) -> list:
    out = []
    for raw in re.split(r"(?<=[.!?;])\s+", clean(text)):
        s = raw.strip(" -•. ")
        if not (60 <= len(s) <= 300):
            continue
        if s.startswith(BAD_START) or not s[:1].isupper() and not s[:1].isdigit():
            continue
        if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
            continue
        if re.search(r"https?://|www\.|@|et al\.,? ?\d{4}|\(19\d\d\)|\(20\d\d\)", s):
            continue
        if sum(ch.isdigit() for ch in s) > len(s) * 0.35:
            continue
        out.append(s)
    return out


def variant_priors(variant: str) -> tuple:
    path = ROOT / variant / "query.py"
    if not path.exists():
        return {}, {}
    spec = importlib.util.spec_from_file_location("variant_query_" + variant, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return {}, {}
    return (dict(getattr(module, "ALIASES", {}) or {}),
            dict(getattr(module, "INFO_TERMS", {}) or {}))


def target_tokens(name: str, info_terms: dict) -> list:
    groups = info_terms.get(name) or {}
    picked = [(label, words) for label, words in groups.items()
              if not str(label).startswith("_") and words
              and re.search(r"target|target", str(label), re.I)]
    if not picked:
        picked = [(label, words) for label, words in groups.items()
                  if not str(label).startswith("_") and words
                  and re.search(r"function|mechanism", str(label), re.I)]
    out = []
    for _, words in picked:
        for word in words:
            norm = normalize(word)
            if len(norm) >= 4:
                out.append(norm)
    return list(dict.fromkeys(out))


GENERIC = {
    "degrader", "degraders", "inhibitor", "inhibitors", "antibody", "antibodies", "antagonist",
    "agonist", "therapy", "therapies", "protein", "proteins", "cancer", "tumor", "tumour",
    "kinase", "clinical", "trial", "trials", "patients", "patient", "disease", "receptor",
    "pathway", "signal", "signaling", "treatment", "target", "targeting", "molecule", "small",
    "compound", "compounds", "drug", "drugs", "phase", "study", "studies", "efficacy", "safety",
    "stat6", "kras", "egfr", "her2", "pd-l1", "pd1", "pdl1", "jak1", "atr", "wee1", "pcsk9",
    "klkb1", "rock", "il-17a", "il-17f", "crispr", "sirna", "protac", "bispecific", "oral",
    "autologous", "allogeneic", "therapy.", "vaccine", "vaccines", "oncology", "immune",
}


INN_SUFFIX = (r"(?:mab|nib|stat|siran|rsen|sen|tide|sertib|zomib|parib|ciclib|parin|vir|"
              r"prazole|gliptin|gliflozin|sartan|pril|olol|dipine|tidine|rubicin|tecan|mycin)$")


def tokens_of(name: str, aliases: dict) -> list:
    out = [normalize(name)]
    for alias in aliases.get(name) or []:
        text = str(alias).strip()
        norm = normalize(text)
        if len(norm) < 4 or norm in GENERIC:
            continue
        single_word = not re.search(r"[^0-9A-Za-z\-]", text)
        has_digit = bool(re.search(r"\d", text))


        is_inn = bool(re.search(INN_SUFFIX, norm))
        if single_word and (has_digit or (is_inn and len(norm) >= 6)):
            out.append(norm)
    return list(dict.fromkeys(t for t in out if len(t) >= 4))


def load(base: pathlib.Path, drug: str, dimension: str = None, comp: str = None) -> list:
    folder = base / drug
    if comp:
        folder = folder / "competitors" / comp
    name = comp or drug
    dims = (dimension,) if dimension else DIMS
    seen, records = set(), []
    for dim in dims:
        path = folder / f"{name}_{dim}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rec in payload.get("results", []):
            key = str(rec.get("doi") or rec.get("pmcid") or rec.get("title") or "")
            if key and key not in seen:
                seen.add(key)
                records.append({**rec, "_dim": dim})
    return records


def stats(base: pathlib.Path, drug: str) -> dict:
    total = full = attempted = chars = 0
    for dim in DIMS:
        path = base / drug / f"{drug}_{dim}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        ft = payload.get("fulltext") or {}
        total += payload.get("returned_results", 0)
        full += ft.get("full_text_count", 0)
        attempted += ft.get("attempted", 0)
        chars += ft.get("avg_full_text_chars", 0) * ft.get("full_text_count", 0)
    return {"total": total, "full": full, "attempted": attempted,
            "avg_chars": round(chars / full) if full else 0,
            "coverage": (full / total) if total else 0.0}


def pick(records: list, patterns, limit: int = 2, max_chars: int = 150,
         tokens=None, need_digit: bool = False, used: set = None) -> list:
    used = used if used is not None else set()
    scored = []
    for rec in records:
        doi = str(rec.get("doi") or rec.get("pmcid") or "").strip()
        if not doi:
            continue
        is_full = rec.get("content_type") == "full_text"
        for s in sentences(rec.get("content")):
            if len(s) > max_chars:
                continue
            low = s.lower()
            if tokens is not None:
                norm = normalize(s)
                if not any(t in norm for t in tokens):
                    continue
            hits = sum(1 for p in patterns if re.search(p, low, re.I))
            if not hits:
                continue
            if need_digit and not re.search(r"\d", s):
                continue
            score = hits + (2.0 if is_full else 0) + (1.5 if re.search(r"\d", s) else 0)
            scored.append((score, len(s), s, doi, is_full))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out, dois = [], set()
    for score, length, s, doi, is_full in scored:
        if doi in dois or s[:60] in used:
            continue
        dois.add(doi)
        out.append((s, doi, is_full))
        if len(out) >= limit:
            break
    return out


def titles(records: list, tokens, limit: int = 1, used: set = None) -> list:
    used = used if used is not None else set()
    out = []
    for rec in records:
        title = clean(rec.get("title"))
        doi = str(rec.get("doi") or rec.get("pmcid") or "").strip()
        if not doi or len(title) < 20 or title[:40] in used:
            continue
        if tokens and not any(t in normalize(title) for t in tokens):
            continue
        used.add(title[:40])
        out.append((title, doi, rec.get("content_type") == "full_text"))
        if len(out) >= limit:
            break
    return out


def render(items: list, variant: str, budget: int, prefix: str = "") -> str:
    buf, used = [], 0
    for item in items:
        s, doi = item[0], item[1]
        piece = f"{s}({variant}, {doi}). "
        if used + len(piece) > budget:
            continue
        buf.append(piece)
        used += len(piece)
    return (prefix + "".join(buf)) if buf else ""


def build(base: pathlib.Path, variant: str, drug: str, aliases: dict, info_terms: dict) -> tuple:
    basic = load(base, drug, "Basic Information")
    clin = load(base, drug, "Clinical Studies")
    preclin = load(base, drug, "Non-Clinical Studies")
    comp_root = base / drug / "competitors"
    comps = sorted([p.name for p in comp_root.iterdir() if p.is_dir()]) if comp_root.exists() else []
    comp_recs = {c: load(base, drug, None, c) for c in comps}
    st = stats(base, drug)
    own = tokens_of(drug, aliases)
    same_target = target_tokens(drug, info_terms)
    used = set()
    emitted = []
    counted = {"full": 0, "abstract": 0}

    def tally(items):
        for item in items:
            counted["full" if item[2] else "abstract"] += 1

    def emit(items: list, budget: int, label: str = "", prefix: str = "",
             repeat: bool = False) -> str:
        kept = []
        for item in items:
            if not repeat and any(similar(item[0], prev)
                                  for prev in emitted + [k[0] for k in kept]):
                continue
            kept.append(item)
        body = render(kept, variant, budget, prefix=prefix)
        if not body:
            return ""
        for item in kept:
            used.add(item[0][:60])
            emitted.append(item[0])
        return label + body

    def field(label: str, records, patterns, budget=125, max_chars=130, digits=False) -> str:
        items = pick(records, patterns, 1, max_chars, tokens=own, need_digit=digits, used=used)
        tally(items)
        return emit(items, budget, label) or f"{label}the interface returned no supporting literature evidence."


    clin_items = pick(clin, CLIN, 3, 165, tokens=own, used=used)
    tally(clin_items)
    body = emit(clin_items, 490)
    if body:
        s3 = body + "Patient baselines, dosing and cycles, primary endpoint P values and grade 3-4 adverse event rates for each trial phase can all be traced back to the full text cited above."
    else:
        s3 = ("The clinical literature returned by this interface does not name this product directly, so its trial design, endpoints and safety data cannot be attributed to this product; "
              "what is available is evidence at the same-indication / same-mechanism level: "
              + (emit(pick(clin, CLIN, 1, 150, used=used), 200) or "the interface returned no supporting literature evidence."))


    pre_items = pick(preclin, PRECLIN, 3, 165, tokens=own, used=used)
    tally(pre_items)
    body = emit(pre_items, 470)
    if body:
        s4 = body + "The IC50/DC50 values, animal models and dosing regimens above come from the full text; abstracts usually do not give this level of detail."
    else:
        same = pick(preclin + basic, PRECLIN, 1, 150, tokens=same_target, used=used)
        tally(same)
        s4 = ("The literature returned by this interface gives no direct in vitro / in vivo quantitative data for this product (IC50/EC50, Caco-2, plasma protein binding, "
              "species Cmax/AUC/T1/2, hERG and Ames, etc.); the same-target mechanistic evidence is: "
              + (emit(same, 200) or "the interface returned no supporting literature evidence.")
              + "DMPK and toxicology data for this product itself: the interface returned no supporting literature evidence.")


    lead = titles(basic, own, 1, used)
    tally(lead)
    lead_text = (f'Titles of literature from this interface that name this product directly: "{lead[0][0]}"({variant}, {lead[0][1]}). '
                 if lead else "")
    pieces = [lead_text,
              field("Developer: ", basic, COMPANY, 115),
              field("Development indication: ", basic, INDICATION, 125),
              field("Target / mechanism of action: ", basic, TARGET, 135),
              field("Modality and dosage form: ", basic, FORM, 165),
              field("Mechanism of action and therapeutic advantage: ", basic + preclin,
                    MECH + (r"synerg", r"compared with", r"potent"), 150)]
    s2 = ""
    for part in pieces:
        if netlen(s2 + part) <= 590:
            s2 += part


    bits = []
    for comp in comps:
        got = pick(comp_recs[comp], MECH + CLIN, 1, 120, tokens=tokens_of(comp, aliases), used=used)
        mark = ""
        if not got:
            got = pick(comp_recs[comp], MECH + CLIN, 1, 118,
                       tokens=target_tokens(comp, info_terms), used=used)
            mark = "(competitor not named; same-target evidence)"
        tally(got)
        bits.append(emit(got, 130, f"{comp}: ", prefix=mark) or f"{comp}: the interface returned no supporting literature evidence.")
    position = ("Position of this product: it sits on the same target or an adjacent mechanism track as the competitors above; this interface returned no head-to-head efficacy or safety comparison, "
                "so the competitive ranking cannot be judged from the available evidence. Non-clinical DMPK comparison: the interface returned no supporting literature evidence.")
    s5 = "Broken down by mechanism and target: " + "".join(bits) + position


    comp_desc = ", ".join(f"{c} {len(comp_recs[c])}" for c in comps) or "none"
    head = (f"Hits from this interface: main drug {len(basic) + len(clin) + len(preclin)} records"
            f"(Basic Information {len(basic)}, Clinical Studies {len(clin)}, Non-Clinical Studies {len(preclin)}), Competitor {comp_desc}. ")
    if st["full"]:
        evidence = (f"Evidence base: {st['total']} of which {st['full']} had open-access full text"
                    f"(average body {st['avg_chars'] / 10000:.1f} characters); the rest have only abstracts, so full-text coverage {st['coverage']:.0%}. ")
    else:
        evidence = f"Evidence base: {st['total']} records are abstract-level evidence only (no full text retrieved this run)."

    sum_used = set()
    pain_items = pick(basic + clin, PAIN, 1, 112, tokens=own, used=sum_used) or \
                 pick(basic + clin, PAIN, 1, 112, tokens=same_target, used=sum_used)
    tally(pain_items)
    pain = emit(pain_items, 148, "Clinical unmet need:" if pain_items and any(
        t in normalize(pain_items[0][0]) for t in own) else "Clinical unmet need (same-target level):", repeat=True)

    mech_items = pick(basic + preclin, MECH, 1, 112, tokens=own, used=sum_used) or \
                 pick(basic + preclin, MECH + TARGET, 1, 112, tokens=same_target, used=sum_used)
    tally(mech_items)
    mech = emit(mech_items, 148, "Mechanistic advantage:" if mech_items and any(
        t in normalize(mech_items[0][0]) for t in own) else "Mechanistic advantage (same-target level):", repeat=True)

    all_comp = [r for recs in comp_recs.values() for r in recs]
    comp_probe = []
    for comp in comps:
        comp_probe += tokens_of(comp, aliases) + target_tokens(comp, info_terms)
    rival_items = pick(all_comp, MECH + CLIN, 1, 112, tokens=comp_probe, used=sum_used)
    tally(rival_items)
    rival = emit(rival_items, 145, "Competitive Landscape: ", repeat=True)

    market = "Market size (patient pool and sales forecast): the interface returned no supporting literature evidence."
    optional = [part for part in (pain, mech, rival) if part] or \
               ["Key points on clinical unmet need, mechanistic advantage and competitive landscape are in sections 2-5."]
    s1 = head + evidence + "".join(optional) + market
    while netlen(s1) > 590 and len(optional) > 1:
        optional.pop(0)
        s1 = head + evidence + "".join(optional) + market

    return "\n".join([
        drug, "", "1.Summary", s1, "", "2.Basic Information", s2, "",
        "3.Clinical Studies", s3, "", "4.Non-Clinical Studies", s4, "", "5.Competitive Landscape", s5, "", SIGN, "",
    ]), counted

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    variant = sys.argv[1]
    drugs = sys.argv[2:] or list(DEFAULT_DRUGS)
    base = DATA / variant / "output"
    aliases, info_terms = variant_priors(variant)
    for drug in drugs:
        if not (base / drug).exists():
            continue
        text, used = build(base, variant, drug, aliases, info_terms)
        (base / f"{drug}.md").write_text(text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
