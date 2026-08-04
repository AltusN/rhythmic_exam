from decimal import Decimal

import pytest

from scoring.aggregate import grade, score_component
from scoring.types import GradeBand


@pytest.fixture
def grade_bands():
    return [
        GradeBand(name="Fail", minimum=Decimal("0")),
        GradeBand(name="Pass", minimum=Decimal("50")),
        GradeBand(name="Good", minimum=Decimal("65")),
        GradeBand(name="Very Good", minimum=Decimal("80")),
        GradeBand(name="Excellent", minimum=Decimal("90")),
    ]


##-- Score component tests --##


def test_score_component_single_value():
    assert score_component([Decimal("100")]) == Decimal("100")


def test_score_component_mean_not_sum():
    assert score_component([Decimal("100"), Decimal("50")]) == Decimal("75")


def test_score_component_large_sequence():
    # a large of scores must return the mean not the sum
    assert score_component([Decimal("100")] * 20) == Decimal("100")


def test_score_component_even_larger_sequence():
    # the amount in of values in the sequence should not matter, the mean should be returned
    assert score_component([Decimal("100")] * 25) == Decimal("100")


def test_score_component_round_2dp():
    assert score_component([Decimal("100"), Decimal("100"), Decimal("50")]) == Decimal(
        "83.33"
    )


def test_score_component_rounds_half_up_at_2dp():
    assert score_component([Decimal("83.34"), Decimal("83.35")]) == Decimal("83.35")


def test_score_component_empty_sequence_raises():
    with pytest.raises(
        ValueError, match="Cannot compute score component of an empty sequence"
    ):
        score_component([])


##-- Grade tests --##


def test_grade_top(grade_bands):
    assert grade(percentage=Decimal("100"), bands=grade_bands) == "Excellent"


def test_grade_high_is_inclusive(grade_bands):
    assert grade(percentage=Decimal("90"), bands=grade_bands) == "Excellent"


def test_grade_just_below_high(grade_bands):
    assert grade(percentage=Decimal("89.99"), bands=grade_bands) == "Very Good"


def test_grade_mid(grade_bands):
    # boundry
    assert grade(percentage=Decimal("65"), bands=grade_bands) == "Good"


def test_grade_low(grade_bands):
    assert grade(percentage=Decimal("50"), bands=grade_bands) == "Pass"


def test_grade_uses_rounded_score_component_at_pass_boundary(grade_bands):
    """Feed the rounded mean into grade and assert it lands in the Pass band."""
    assert (
        grade(
            percentage=score_component([Decimal("49.99"), Decimal("50.00")]),
            bands=grade_bands,
        )
        == "Pass"
    )


def test_grade_fail(grade_bands):
    assert grade(percentage=Decimal("49.99"), bands=grade_bands) == "Fail"


def test_grade_zero(grade_bands):
    assert grade(percentage=Decimal("0"), bands=grade_bands) == "Fail"


def test_grade_below_every_band_raises():
    # A grade band that has a minimum of 50, and test that a percentage below that raises an error
    single_band_above_zero = [GradeBand(name="Good", minimum=Decimal("50"))]

    with pytest.raises(ValueError, match="is below the minimum of all grade bands"):
        grade(percentage=Decimal("49"), bands=single_band_above_zero)


def test_grade_bands_out_of_order():
    # Ordering of the bands must not matter to what score is returned.
    out_of_order_bands = [
        GradeBand(name="Pass", minimum=Decimal("50")),
        GradeBand(name="Very Good", minimum=Decimal("80")),
        GradeBand(name="Fail", minimum=Decimal("0")),
        GradeBand(name="Excellent", minimum=Decimal("100")),
        GradeBand(name="Good", minimum=Decimal("65")),
    ]

    assert grade(percentage=Decimal("99.99"), bands=out_of_order_bands) == "Very Good"


def test_grade_empty_bands_raises():
    with pytest.raises(ValueError, match="Grade bands sequence cannot be empty"):
        grade(percentage=Decimal("50"), bands=[])
