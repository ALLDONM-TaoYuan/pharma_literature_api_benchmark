"""config package init: test matrix and text-level helpers (keyword groups now live in each interface script)."""

import re


DRUG_DIMENSIONS = ("Basic Information", "Clinical Studies", "Non-Clinical Studies")


DRUG_SECTIONS = (
    "Summary",
    "Basic Information",
    "Clinical Studies",
    "Non-Clinical Studies",
    "Competitive Landscape",
    "References / Source Catalog",
)


TRAILING_NOTE = re.compile(r"[((][^()()]*[))]\s*$")


def split_query_lines(cell_text: str, extra_terms: dict = None) -> list:
    extra_terms = extra_terms or {}
    groups = []
    for raw in str(cell_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('"target"') or line.startswith('"Indication"'):
            key = "target" if line.startswith('"target"') else "indication"
            words = list(extra_terms.get(key) or [])
            line = TRAILING_NOTE.sub("", line).strip()
        else:
            words = [part.strip().strip('"') for part in re.split(r"\bOR\b", line, flags=re.I)]
        words = [word for word in words if word]
        if words:
            groups.append({"raw": line, "words": words})
    return groups


def drug_forms(name: str) -> list:
    name = str(name or "").strip()
    if not name:
        return []
    forms = [name, name.replace("-", ""), name.replace("-", " ")]
    return list(dict.fromkeys(form for form in forms if form))


def needs_quotes(word: str) -> bool:
    return bool(re.search(r"[^0-9A-Za-z]", word))


def phrase(word: str) -> str:
    return f'"{word}"' if needs_quotes(word) else word


def quoted_phrase(word: str) -> str:
    text = str(word or "").strip()
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"' if text else ""


def flatten_words(groups: list) -> list:
    words = []
    for group in groups:
        words.extend(group["words"])
    return list(dict.fromkeys(words))
