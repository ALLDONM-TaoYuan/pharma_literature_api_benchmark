"""ES4: ES interface plus manual info matching (multi-round aliases plus manual info concept groups)."""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import pathlib
sys.path.append(str(next(p for p in pathlib.Path(__file__).resolve().parents
                             if (p / "src" / "__init__.py").exists())))
from src.paths import variant_data  # noqa: E402
DATA = variant_data("disease", "ES4")
sys.path.insert(0, str(HERE.parent / "ES2"))


from config import settings
import ES2_query as es2


INFO_TERMS = {'HIV-1 AIDS': {'cause': ['HIV-1', 'retrovirus', 'CD4 depletion'],
                'manifestation': ['angioedema', 'opportunistic infection', 'CD4 T cell depletion'],
                'mechanism': ['bradykinin', 'plasma kallikrein', 'immune activation']},
 'ischemic heart disease': {'cause': ['atherosclerosis', 'coronary plaque'],
                            'manifestation': ['angina', 'myocardial infarction', 'exertional dyspnea'],
                            'mechanism': ['plaque rupture', 'thrombosis', 'ischemia']},
 'spinal muscular atrophy': {'cause': ['SMN1', 'SMN1 deletion', 'autosomal recessive'],
                             'manifestation': ['muscle weakness', 'motor milestone delay'],
                             'mechanism': ['SMN protein', 'motor neuron degeneration', 'SMN2 splicing']},
 'EGFR Exon20ins mutation non-small cell lung cancer': {'cause': ['EGFR exon 20 insertion',
                                                                  'driver mutation'],
                                                        'manifestation': ['non-small cell lung '
                                                                          'cancer',
                                                                          'brain metastasis'],
                                                        'mechanism': ['tyrosine kinase activation',
                                                                      'structural insertion']},
 'Her2-positive breast cancer': {'cause': ['HER2', 'ERBB2', 'amplification'],
                                 'manifestation': ['breast cancer', 'brain metastasis'],
                                 'mechanism': ['receptor dimerization', 'PI3K signaling']}}


KEYWORDS = es2.KEYWORDS
DIMENSIONS = ('Basic Information', 'Clinical Studies', 'Pre-Clinical Studies')
MODE = "ES4"


INFO_MODE = "AND"


NARROW_IN_ALL_ROUNDS = False


from config import disease_forms


def base_forms(entity):
    return disease_forms(entity)


def info_groups(entity):
    return INFO_TERMS.get(entity, {})


def info_clauses(entity):
    clauses = []
    for label, words in info_groups(entity).items():
        items = [es2.es_phrase(word) for word in words or [] if str(word).strip()]
        if items:
            clauses.append("(" + " OR ".join(items) + ")")
    return clauses


def keyword_groups(dimension):
    return es2.keyword_groups(dimension)


def build_query_text(entity, dimension=None, anchor=None, info_group=None, with_narrow=True):
    if anchor is None:
        names = base_forms(entity)
    elif isinstance(anchor, str):
        names = [anchor]
    else:
        names = list(anchor)
    parts = [quoted_phrase(name) for name in names if str(name).strip()]
    clauses = []
    body = " OR ".join(
        es2.es_phrase(word) for word in first_group(dimension)[: settings.ES_WORDS_LIMIT]
    )
    if body and with_narrow:
        clauses.append("(" + body + ")")
    if info_group:
        label, words = info_group
        items = [es2.es_phrase(word) for word in words or [] if str(word).strip()]
        if items:
            if INFO_MODE == "OR":
                parts += items
            else:
                clauses.append("(" + " OR ".join(items) + ")")
    anchor_text = " OR ".join(parts)
    if not anchor_text:
        return " AND ".join(clauses)
    return " AND ".join(["(" + anchor_text + ")"] + clauses)


def ladder_forms(entity: str) -> list:
    getter = getattr(es2, "ladder_forms", None)
    if getter is None:
        return []
    return list(getter(entity))

def quoted_phrase(word: str) -> str:
    getter = getattr(es2, "quoted_phrase", None)
    if getter is not None:
        return getter(word)
    try:
        from config import quoted_phrase as _qp

        return _qp(word)
    except ImportError:
        from config import phrase as _p

        return _p(word)


def first_group(dimension: str) -> list:
    getter = getattr(es2, "first_group", None)
    if getter is not None:
        return list(getter(dimension))
    for group in es2.keyword_groups(dimension):
        if group.get("words"):
            return list(group["words"])
    return []


def info_group_list(entity):
    groups = dict(info_groups(entity))
    groups.pop("_mode", None)
    return list(groups.items())


def build_payload(entity, dimension=None, anchor=None, info_group=None, size=None, with_narrow=True):
    payload = {
        "query": {
            "query_string": {
                "fields": list(settings.ES_SEARCH_FIELDS),
                "query": build_query_text(entity, dimension, anchor, info_group, with_narrow),
            }
        },
        "_source": list(settings.ES_SOURCE_FIELDS),
        "size": size or settings.TOP_N,
        "track_total_hits": True,
    }
    payload.update(es2.REQUEST_EXTRA)
    return payload


def run_rounds(entity, dimension=None, size=10):
    if MODE == "ES4":
        anchors = list(es2.aliases_of(entity))
        for form in ladder_forms(entity):
            if form not in anchors:
                anchors.append(form)
    else:
        anchors = [None]
    groups = info_group_list(entity)
    plan = []
    for anchor in anchors:
        plan.append((anchor, None, True))
        for group in groups:
            plan.append((anchor, group, NARROW_IN_ALL_ROUNDS))
    rounds, merged, seen, total_sum = [], [], set(), 0
    for anchor, group, with_narrow in plan:
        payload = build_payload(entity, dimension, anchor, group, size=size, with_narrow=with_narrow)
        data = es2.es_search(payload, size=size)
        total, hits = es2.summarize(data)
        total_sum += total
        rounds.append({
            "query": payload["query"]["query_string"]["query"],
            "total": total,
            "fetched": len(hits),
            "anchor": anchor or "(original-name form)",
            "info_group": group[0] if group else "",
            "with_narrow": with_narrow,
        })
        for hit in hits:
            key = str((hit.get("_source") or {}).get("doi") or hit.get("_id"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    return rounds, total_sum, merged


def compare(entity, dimension):
    base_rounds, base_sum, base_hits = es2.run_rounds(entity, dimension, size=settings.TOP_N)
    rounds, round_sum, new_hits = run_rounds(entity, dimension, size=settings.TOP_N)
    key = lambda hit: str((hit.get("_source") or {}).get("doi") or hit.get("_id"))
    base_dois = {key(hit) for hit in base_hits}
    new_dois = {key(hit) for hit in new_hits}


    only_new = [hit for hit in new_hits if key(hit) in (new_dois - base_dois)]
    if only_new:
        es2.show_hits(only_new)


def run(entity, dimension="Basic Information"):
    rounds, round_sum, hits = run_rounds(entity, dimension, size=settings.TOP_N)

    for item in rounds:
        pass

    es2.show_hits(hits)


def main():
    argv = sys.argv[1:]
    if not argv:
        for name in es2.entities():
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
