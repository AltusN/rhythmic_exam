from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from scoring.types import GradeBand


def score_component(item_percentages: Sequence[Decimal]) -> Decimal:
    """
    Compute the mean of a sequence of item percentages, rounded to 2 decimal places.
    Raises ValueError if the sequence is empty.
    """
    if not item_percentages:
        raise ValueError("Cannot compute score component of an empty sequence")
    mean = sum(item_percentages) / Decimal(len(item_percentages))
    return mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def grade(*, percentage: Decimal, bands: Sequence[GradeBand]) -> str:
    """
    Given a percentage and a sequence of GradeBand objects, return the name of the highest band
    for which the percentage is greater than or equal to the band's minimum.
    If no bands match, raises a ValueError. Ordering of the bands is irrelevant.
    """
    if not bands:
        raise ValueError("Grade bands sequence cannot be empty")

    qualifying_bands = [band for band in bands if percentage >= band.minimum]

    if not qualifying_bands:
        raise ValueError(
            f"Percentage {percentage} is below the minimum of all grade bands"
        )

    return max(qualifying_bands, key=lambda band: band.minimum).name
