from decimal import Decimal

import pytest

from exams.awards import (
    AspectResult,
    BandsDisagree,
    Category,
    DimensionGrade,
    UnknownGrade,
    dimension_grades,
    examination_category,
)
from scoring import GradeBand

# No django_db marker in this file: the award rules are pure functions.

# General Judges' Rules section 2.6, as published by FIG. The two band sets differ:
# Excellent is 80% for Difficulty and 90% for Artistry and Execution.
DIFFICULTY_BANDS = (
    GradeBand("Fail", Decimal("0")),
    GradeBand("Pass", Decimal("50")),
    GradeBand("Good", Decimal("60")),
    GradeBand("Very Good", Decimal("70")),
    GradeBand("Excellent", Decimal("80")),
)
ARTISTRY_EXECUTION_BANDS = (
    GradeBand("Fail", Decimal("0")),
    GradeBand("Pass", Decimal("50")),
    GradeBand("Good", Decimal("65")),
    GradeBand("Very Good", Decimal("80")),
    GradeBand("Excellent", Decimal("90")),
)

# Category 1 is the only row that is not uniform.
REQUIREMENTS = {
    (category, dimension): minimum
    for category, minimums in {
        1: ("Excellent", "Very Good", "Very Good"),
        2: ("Very Good", "Very Good", "Very Good"),
        3: ("Good", "Good", "Good"),
        4: ("Pass", "Pass", "Pass"),
    }.items()
    for dimension, minimum in zip(
        ("DIFFICULTY", "EXECUTION", "ARTISTRY"), minimums, strict=True
    )
}


def _aspect(percentage, grade, bands=DIFFICULTY_BANDS):
    return AspectResult(percentage=Decimal(percentage), grade=grade, bands=bands)


def _results(
    da="75.00", db="75.00", av=("85.00", "Very Good"), ex=("95.00", "Excellent")
):
    return {
        "DA": _aspect(da, "unused"),
        "DB": _aspect(db, "unused"),
        "AV": _aspect(*av, ARTISTRY_EXECUTION_BANDS),
        "EX": _aspect(*ex, ARTISTRY_EXECUTION_BANDS),
    }


def test_difficulty_is_the_mean_of_the_rounded_scores():
    # CLAUDE.md, 2026-08-08: 79.90 and 80.09 are what the candidate is shown, and
    # their mean, 79.995, rounds half-up to 80.00 -- Excellent. Graded before it is
    # quantized, 79.995 falls below the 80 edge and gives Very Good.
    grades = dimension_grades(_results(da="79.90", db="80.09"))

    assert grades["DIFFICULTY"] == DimensionGrade("Excellent", DIFFICULTY_BANDS)


def test_difficulty_rounds_half_up():
    # The mean is 79.985: half-up gives 79.99, half-even 79.98. A band whose edge is
    # exactly 79.99 turns that one-hundredth into a different grade.
    edge = (GradeBand("Below", Decimal("0")), GradeBand("At edge", Decimal("79.99")))
    results = {
        **_results(),
        "DA": _aspect("79.98", "unused", edge),
        "DB": _aspect("79.99", "unused", edge),
    }

    assert dimension_grades(results)["DIFFICULTY"].grade == "At edge"


def test_execution_and_artistry_are_read_as_stored():
    # Different grades for the two, so a mutant swapping them dies.
    grades = dimension_grades(_results())

    assert (grades["EXECUTION"].grade, grades["ARTISTRY"].grade) == (
        "Excellent",
        "Very Good",
    )


def test_differing_difficulty_bands_raise():
    results = {**_results(), "DB": _aspect("75.00", "unused", ARTISTRY_EXECUTION_BANDS)}

    with pytest.raises(BandsDisagree):
        dimension_grades(results)


def _dimensions(difficulty, execution, artistry):
    return {
        "DIFFICULTY": DimensionGrade(difficulty, DIFFICULTY_BANDS),
        "EXECUTION": DimensionGrade(execution, ARTISTRY_EXECUTION_BANDS),
        "ARTISTRY": DimensionGrade(artistry, ARTISTRY_EXECUTION_BANDS),
    }


@pytest.mark.parametrize(
    ("grades", "expected"),
    [
        (("Excellent", "Very Good", "Very Good"), Category.ONE),
        # Difficulty only Very Good while the others are Excellent: Category 2.
        # A uniform Category 1 row would award 1 here and nowhere else.
        (("Very Good", "Excellent", "Excellent"), Category.TWO),
        (("Excellent", "Excellent", "Good"), Category.THREE),
        (("Pass", "Pass", "Pass"), Category.FOUR),
        (("Excellent", "Excellent", "Fail"), Category.FAIL),
        # By rank, Pass caps this at Category 4. By name, "Pass" >= "Good" is true
        # as a string, so comparing names awards Category 3.
        (("Very Good", "Pass", "Pass"), Category.FOUR),
    ],
    ids=[
        "category-1",
        "category-1-asymmetry",
        "weakest-dimension-caps",
        "category-4",
        "fail",
        "ranks-not-names",
    ],
)
def test_examination_category(grades, expected):
    assert examination_category(_dimensions(*grades), REQUIREMENTS) is expected


def test_an_unknown_minimum_grade_raises():
    requirements = {**REQUIREMENTS, (1, "DIFFICULTY"): "Excelent"}

    with pytest.raises(UnknownGrade):
        examination_category(
            _dimensions("Excellent", "Very Good", "Very Good"), requirements
        )
