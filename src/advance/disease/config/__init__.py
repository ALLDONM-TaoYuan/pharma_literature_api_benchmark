"""config package init: word lists and text helpers shared by the disease interface tests and the per-interface query scripts."""

import re


DISEASE_DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies")


DISEASE_KEYWORDS = {
    "Basic Information": [
        ["epidemiology", "prevalence", "incidence"],
        ["etiology", "pathogenesis", "pathophysiology"],
        ["genetic mutation", "molecular mechanism", "signaling pathway"],
        ["biomarker", "molecular marker", "biomarkers"],
        ["classification", "subtype", "staging", "diagnostic criteria"],
        ["clinical manifestation", "symptoms", "diagnosis"],
        ["prognosis", "risk factors"],
    ],
    "Clinical Studies": [
        ["clinical trial", "randomized controlled trial", "phase 3"],
        ["treatment", "therapy", "guideline", "standard of care"],
        ["efficacy", "overall survival", "progression-free survival", "response rate"],
        ["safety", "adverse events", "tolerability"],
        ["real-world", "systematic review", "meta-analysis"],
    ],
    "Pre-Clinical Studies": [
        ["in vivo", "animal model", "mouse model", "xenograft"],
        ["in vitro", "cell line", "organoid"],
        ["pathology", "histopathology", "immunohistochemistry"],
        ["knockout mice", "transgenic model", "disease model"],
        ["drug target", "target validation", "mechanism of action"],
    ],
}


def disease_keyword_groups(dimension: str) -> list:
    groups = []
    for words in DISEASE_KEYWORDS.get(dimension, []):
        groups.append({"raw": " OR ".join(words), "words": list(words)})
    return groups


def needs_quotes(word: str) -> bool:
    return bool(re.search(r"[^0-9A-Za-z]", word))


def phrase(word: str) -> str:
    return f'"{word}"' if needs_quotes(word) else word


def flatten_words(groups: list) -> list:
    words = []
    for group in groups:
        words.extend(group["words"])
    return list(dict.fromkeys(words))


def quoted_phrase(word: str) -> str:
    text = str(word or "").strip()
    if not text:
        return ""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def disease_forms(name: str) -> list:
    text = str(name or "").strip()
    if not text:
        return []
    forms = [text]
    if "-" in text:
        forms.append(text.replace("-", " "))
        forms.append(text.replace("-", ""))
    return list(dict.fromkeys(form for form in forms if form))
