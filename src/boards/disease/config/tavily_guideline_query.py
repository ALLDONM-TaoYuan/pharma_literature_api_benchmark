"""Query script for the tavily advanced search (disease guidelines / professional resources)."""

from config import disease_forms


NATURAL_QUERIES = {
    "Basic Information": [
        "{disease} clinical practice guideline",
        "{disease} diagnosis classification guideline",
    ],
    "Clinical Studies": [
        "{disease} treatment guideline recommendations",
        "{disease} guideline NCCN ESMO WHO CSCO",
    ],
    "Pre-Clinical Studies": [
        "{disease} guideline preclinical translational recommendations",
    ],
}


TARGET_QUERY = "{disease} guideline"
TARGET_DOMAINS = [
    "nccn.org",
    "esmo.org",
    "who.int",
    "nice.org.uk",
    "ascopubs.org",
    "csco.org.cn",
]


GUIDELINE_ORGS = {
    "nccn.org": "NCCN (National Comprehensive Cancer Network)",
    "jnccn.org": "JNCCN (the official journal of NCCN)",
    "esmo.org": "ESMO (European Society for Medical Oncology)",
    "oncologypro.esmo.org": "the ESMO official learning platform",
    "annalsofoncology.org": "Annals of Oncology (the official journal of ESMO)",
    "ascopubs.org": "ASCO (American Society of Clinical Oncology)",
    "who.int": "WHO (World Health Organization)",
    "nice.org.uk": "NICE (UK National Institute for Health and Care Excellence)",
    "cdc.gov": "CDC (US Centers for Disease Control and Prevention)",
    "clinicalinfo.hiv.gov": "the official US HIV guideline library",
    "hivguidelines.org": "the New York State HIV clinical guidelines",
    "csco.org.cn": "CSCO (Chinese Society of Clinical Oncology)",
    "escardio.org": "ESC (European Society of Cardiology)",
    "acc.org": "ACC (American College of Cardiology)",
    "ahajournals.org": "AHA/ASA (American Heart Association / American Stroke Association)",
    "treat-nmd.org": "TREAT-NMD (the international neuromuscular disease network)",
    "curesma.org": "Cure SMA (a patient organization issuing standard-of-care recommendations)",
    "patient.info": "Patient (a patient version of the guidelines; low reference value, for hints only)",
    "pubmed.ncbi.nlm.nih.gov": "PubMed (a literature database; may contain guideline entries)",
    "ncbi.nlm.nih.gov": "NCBI (a literature database; may contain guideline entries)",
    "guidelinecentral.com": "Guideline Central (a guideline aggregator)",
    "hivinfo.nih.gov": "the NIH HIV information library (including guidelines)",
    "bhiva.org": "BHIVA (British HIV Association)",
    "idsociety.org": "IDSA (Infectious Diseases Society of America)",
    "iasusa.org": "IAS-USA (International Antiviral Society - USA)",
    "aahivm.org": "AAHIVM (American Academy of HIV Medicine)",
    "doh.gov.ae": "the UAE Ministry of Health",
    "jacc.org": "JACC (Journal of the American College of Cardiology)",
    "onlinecjc.ca": "CJC (Canadian Journal of Cardiology)",
    "acponline.org": "ACP (American College of Physicians)",
    "aafp.org": "AAFP (American Academy of Family Physicians)",
    "cmaj.ca": "CMAJ (Canadian Medical Association Journal)",
    "cap.org": "CAP (College of American Pathologists)",
}


NEWS_SOURCES = ("dailynews.ascopubs.org", "ascopost.com")


LITERATURE_DATABASES = ("pmc.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov")


GUIDELINE_WORDS = (
    "guideline",
    "guidelines",
    "guidance",
    "consensus",
    "recommendation",
    "recommendations",
    "standard of care",
    "treatment algorithm",
    "guideline",
    "consensus",
)


def build_tasks(disease: str, dimension: str = None) -> list:
    name = disease_forms(disease)[0] if disease_forms(disease) else str(disease or "").strip()
    templates = NATURAL_QUERIES.get(dimension, NATURAL_QUERIES["Basic Information"])
    tasks = [
        {"query": template.replace("{disease}", name), "targeted": False, "include_domains": None}
        for template in templates
    ]
    tasks.append({
        "query": TARGET_QUERY.replace("{disease}", name),
        "targeted": True,
        "include_domains": list(TARGET_DOMAINS),
    })
    return tasks


def build_payload(query: str, include_domains=None, max_results: int = None) -> dict:
    payload = {"query": str(query or "").strip(), "search_depth": "advanced"}
    if max_results:
        payload["max_results"] = int(max_results)
    if include_domains:
        payload["include_domains"] = list(include_domains)
    return payload


def domain_of(url: str) -> str:
    text = str(url or "")
    text = text.split("//", 1)[-1]
    text = text.split("/", 1)[0]
    text = text.split("?", 1)[0].split(":", 1)[0].lower()
    return text[4:] if text.startswith("www.") else text


def org_of(domain: str) -> str:
    for news in NEWS_SOURCES:
        if domain == news or domain.endswith("." + news):
            return ""
    for known, label in GUIDELINE_ORGS.items():
        if domain == known or domain.endswith("." + known):
            return label
    return ""


def judge_item(item: dict) -> dict:
    url = str(item.get("url") or "")
    title = str(item.get("title") or "")
    snippet = str(item.get("content") or "")
    domain = domain_of(url)
    org = org_of(domain)
    text = " ".join([title, snippet, url]).lower()
    words = [word for word in GUIDELINE_WORDS if word in text]
    return {
        "domain": domain,
        "org": org,
        "guideline_words": words,
        "is_org_guideline": bool(org),
        "is_publisher_guideline": bool(org) and domain not in LITERATURE_DATABASES,
        "mentions_guideline": bool(words),
    }
