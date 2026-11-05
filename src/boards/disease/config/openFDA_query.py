"""API input conventions for the openFDA interface."""

OPENFDA_FIELD_BY_DIMENSION = {
    "Basic Information": "indications_and_usage",
    "Clinical Studies": "clinical_studies",
    "Pre-Clinical Studies": "nonclinical_toxicology",
}


OPENFDA_DEFAULT_FIELD = "indications_and_usage"


def field_for_dimension(dimension: str) -> str:
    return OPENFDA_FIELD_BY_DIMENSION.get(dimension, OPENFDA_DEFAULT_FIELD)


def build_params(disease: str, groups: list = None, dimension: str = None) -> dict:
    words = [word for word in disease.split() if word]
    body = " AND ".join(words) if words else disease.strip()
    return {
        "search": f"{field_for_dimension(dimension)}:({body})",
        "limit": None,
    }
