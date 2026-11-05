"""config package init: only the "test matrix" and "text-level helpers"; query content belongs to each interface script."""

import re


TARGET_DIMENSIONS = ("Basic Information", "Clinical Studies", "Pre-Clinical Studies", "Druggability Feasibility Study")


GENE_LIKE = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{0,11}$")


def target_terms(name: str) -> list:
    terms = []
    for part in (piece.strip() for piece in str(name or "").split("/")):
        if not part:
            continue
        tokens = part.split()
        gene_like = all(
            GENE_LIKE.match(token) and (any(c.isupper() for c in token) or any(c.isdigit() for c in token))
            for token in tokens
        )
        terms.extend(tokens if len(tokens) > 1 and gene_like else [part])
    return list(dict.fromkeys(terms))


def needs_quotes(word: str) -> bool:
    return bool(re.search(r"[^0-9A-Za-z]", word))


def phrase(word: str) -> str:
    return f'"{word}"' if needs_quotes(word) else word


def flatten_words(groups: list) -> list:
    words = []
    for group in groups:
        words.extend(group["words"])
    return list(dict.fromkeys(words))
