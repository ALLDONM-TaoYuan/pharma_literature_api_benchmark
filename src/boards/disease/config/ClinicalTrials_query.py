"""Query script for the ClinicalTrials.gov interface."""


def build_disease_params(disease: str, groups: list = None) -> dict:
    return {
        "query.cond": disease.strip(),
        "pageSize": None,
        "countTotal": "true",
    }

