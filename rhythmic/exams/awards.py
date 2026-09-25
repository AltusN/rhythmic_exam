"""The examination category, and the bounds on the category awarded. Pure.

General Judges' Rules 2025-2028, section 2.6. Like `exams/eligibility.py` this
imports nothing from Django and touches no database: `exams/certification.py` loads
the rows, calls these, and stores what comes back.
"""

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from scoring import GradeBand, grade, score_component


class Category(enum.IntEnum):
    # FAIL is 5, not 0. Category 1 is best, so "worse" is "numerically greater"
    # everywhere: the drop floor is previous + 2, the first-cycle cap bounds from
    # below in numbers, and FAIL sorts after 4 with no special case. FAIL = 0 would
    # compare as better than Category 1 -- a wrong answer with no error.
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FAIL = 5


class BandsDisagree(ValueError):
    """DA and DB were frozen with different bands, so no band set can grade their
    mean without choosing one side arbitrarily."""


class UnknownGrade(ValueError):
    """A section 2.6 minimum names a grade the band set does not have."""


@dataclass(frozen=True)
class AspectResult:
    percentage: Decimal
    grade: str
    bands: tuple[GradeBand, ...]


@dataclass(frozen=True)
class DimensionGrade:
    # The band set travels with the grade: it is what ranks the grade.
    grade: str
    bands: tuple[GradeBand, ...]


def dimension_grades(results: Mapping[str, AspectResult]) -> dict[str, DimensionGrade]:
    """Section 2.6's three dimensions from the four aspect results.

    Difficulty is the mean of the two STORED, ROUNDED aspect percentages, through
    scoring's own score_component so the rounding is the one used everywhere else
    (decided 2026-08-08: a figure that cannot be recomputed from the numbers on the
    certificate is the one that loses an appeal).
    """
    da, db = results["DA"], results["DB"]
    if da.bands != db.bands:
        raise BandsDisagree(da.bands, db.bands)
    difficulty = score_component([da.percentage, db.percentage])
    return {
        "DIFFICULTY": DimensionGrade(
            grade(percentage=difficulty, bands=da.bands), da.bands
        ),
        "EXECUTION": DimensionGrade(results["EX"].grade, results["EX"].bands),
        "ARTISTRY": DimensionGrade(results["AV"].grade, results["AV"].bands),
    }


def _rank(name: str, bands: Sequence[GradeBand]) -> int:
    # Position in the band set ordered by minimum: Fail 0, Pass 1, and so on. Never
    # compare grade names directly -- as strings "Pass" > "Good" > "Excellent".
    for position, band in enumerate(sorted(bands, key=lambda band: band.minimum)):
        if band.name == name:
            return position
    raise UnknownGrade(name)


def examination_category(
    dimensions: Mapping[str, DimensionGrade],
    requirements: Mapping[tuple[int, str], str],
) -> Category:
    """The best category whose minimums are all met, else FAIL.

    `requirements` maps (category, dimension) to the minimum grade's name. The
    weakest dimension caps the result.
    """
    for category in (Category.ONE, Category.TWO, Category.THREE, Category.FOUR):
        if all(
            _rank(achieved.grade, achieved.bands)
            >= _rank(requirements[category, dimension], achieved.bands)
            for dimension, achieved in dimensions.items()
        ):
            return category
    return Category.FAIL
