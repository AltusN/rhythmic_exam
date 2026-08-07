from decimal import Decimal

import pytest

from scoring.legacy import sagf_legacy_table
from scoring.marking import mark_numeric
from scoring.types import MarkingTable


@pytest.fixture
def legacy_table() -> MarkingTable:
    return sagf_legacy_table()


@pytest.mark.parametrize(
    "response, expert_score, expected",
    [
        ("0", Decimal("1"), Decimal("0")),
        ("0.05", Decimal("1"), Decimal("5")),
        ("0.50", Decimal("1"), Decimal("50")),
        ("0.95", Decimal("1"), Decimal("95")),
        ("1.0", Decimal("1"), Decimal("100")),
        ("3.0", Decimal("1"), Decimal("0")),
    ],
    ids=[
        "difference_1.0",
        "difference_0.95",
        "difference_0.50",
        "difference_0.05",
        "difference_0.0",
        "difference_2.0",
    ],
)
def test_legacy_scheme_marks_by_difference(
    response: str, expert_score: Decimal, expected: Decimal, legacy_table: MarkingTable
) -> None:
    assert mark_numeric(response, expert_score, legacy_table) == expected


def test_f3_unpadded_response_scores_100_not_zero(legacy_table: MarkingTable) -> None:
    """Legacy would not have matched 0.3 to 0.30, but now it does"""
    assert mark_numeric("0.3", Decimal("0.30"), legacy_table) == Decimal("100")


def test_f4_difference_between_steps_floors_into_band(
    legacy_table: MarkingTable,
) -> None:
    """Legacy would have thrown ValueError"""
    assert mark_numeric("0.23", Decimal("0.30"), legacy_table) == Decimal("95")


def test_decimal_marks_avoid_legacy_float_error(legacy_table: MarkingTable) -> None:
    """legacy computed marks as floats, so 2.75 / 5 * 100 came out as 55.00000000000001."""
    assert mark_numeric("1.45", Decimal("1.00"), legacy_table) == Decimal("55")
