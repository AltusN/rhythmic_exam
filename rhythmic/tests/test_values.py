from decimal import Decimal

import pytest

from scoring.values import to_decimal, UnparseableAnswer

def test_garbage_answer():
    with pytest.raises(UnparseableAnswer):
        to_decimal("garbage")

@pytest.mark.parametrize(
    "answer, expected",
    [
        ("1", Decimal("1")),
        ("1.0", Decimal("1.0")),
        ("0.5", Decimal("0.5")),
        ("0.25", Decimal("0.25")),
    ]
)
def test_valid_answer(answer, expected):
    assert to_decimal(answer) == expected

def test_trailing_zeros_do_not_change_the_value():
    #0.3 and 0.30 are equal as decimals, but the string representation is different. 
    # This test ensures that the function treats them as equal.
    # This test's F3 from the specification ensures that trailing zeros do not affect the value of the decimal.
    assert to_decimal("0.3") == to_decimal("0.30")

def test_leading_0_omitted():
    assert to_decimal(".5") == Decimal("0.5")

def test_slash_with_spaces_raises():
    # This ensures division is not performed and that the function raises an error for invalid formats.
    with pytest.raises(UnparseableAnswer):
        to_decimal(" 1 / 2 ")

def test_comma_with_spaces_raises():
    # If the input has spaces around a comma, it should raise an error because it's not a valid decimal format.
    with pytest.raises(UnparseableAnswer):
        to_decimal(" 1 , 2 ")

def test_whitespace_stripped():
    assert to_decimal("  0.75  ") == Decimal("0.75")

def test_decimal_with_decimal_input():
    assert to_decimal(Decimal("0.75")) == Decimal("0.75")

def test_comma_in_string_returns_decimal():
    assert to_decimal("0,75") == Decimal("0.75")

def test_slash_is_not_division():
    # This test ensures that the function does not perform division and instead treats slashes as invalid input.
    # but only if the input is not a valid decimal format. In this case, "0/3" is treated as "0.3" after replacing the slash with a dot.

    assert to_decimal("0/3") == Decimal("0.3")

def test_only_space_in_answer_returns_none():
    assert to_decimal(" ") is None

def test_nan_raises():
    with pytest.raises(UnparseableAnswer):
        to_decimal("NaN")

def test_no_input():
    assert to_decimal("") is None

def test_none_input():
    assert to_decimal(None) is None

