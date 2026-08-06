import pytest

import scoring

EXPORTED_NAMES = [
    "to_decimal",
    "UnparseableAnswer",
    "MarkingTable",
    "BandRow",
    "GradeBand",
    "mark_choice",
    "mark_numeric",
    "score_component",
    "grade",
]


@pytest.mark.parametrize("name", EXPORTED_NAMES)
def test_public_api_name_is_exported(name):
    assert hasattr(scoring, name)


def test_public_api_all():
    assert sorted(EXPORTED_NAMES) == sorted(scoring.__all__)
