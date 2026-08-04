from decimal import Decimal

import pytest

from scoring.marking import mark_choice, mark_numeric
from scoring.values import UnparseableAnswer


@pytest.mark.parametrize(
    "response, correct_option, expected",
    [
        ("A", "A", 100),
        ("A", "B", 0),
        (None, "A", 0),
    ],
    ids=[
        "correct_choice",
        "incorrect_choice",
        "no_response",
    ],
)
def test_mark_choice(response, correct_option, expected):
    assert mark_choice(response, correct_option) == expected


def test_mark_numeric_exact_match(mark_table):
    assert mark_numeric("0.30", Decimal("0.30"), mark_table) == 100


def test_f3_regression(mark_table):
    # F3 regression: previously, this didn't match the fast path,
    # it would then compute the differnce as 0 thus ruturn 0, now it should return 100
    assert mark_numeric("0.3", Decimal("0.30"), mark_table) == 100


def test_f4_regression(mark_table):
    # previously raised valueerror, now should return 100
    assert mark_numeric("0.31", Decimal("0.30"), mark_table) == 100


def test_mark_numeric_below_first_row(mark_table):
    # below the first row, should return the first row's percentage
    assert mark_numeric("0.10", Decimal("0.30"), mark_table) == 50


def test_mark_numeric_no_answer(mark_table):
    # no answer, should return 0
    assert mark_numeric(None, Decimal("0.30"), mark_table) == 0


def test_mark_numeric_select_second_row(mark_table):
    assert mark_numeric("1.85", Decimal("2.00"), mark_table) == 100


def test_mark_numeric_small_difference_lands_in_second_column(mark_table):
    # small difference should land in the second column, which is 90 for the first (0) row
    assert mark_numeric("0.45", Decimal("0.30"), mark_table) == 90


def test_mark_numeric_large_difference_lands_in_last_column(mark_table):
    # large difference should land in the last column, which is 50 for the first (0) row
    assert mark_numeric("0.80", Decimal("0.30"), mark_table) == 50


def test_mark_numeric_unparsable_response(mark_table):
    with pytest.raises(UnparseableAnswer, match="Cannot parse answer"):
        mark_numeric("abc", Decimal("0.30"), mark_table)
