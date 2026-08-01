from decimal import Decimal


def floor_band_index(*, value: Decimal, lower_bounds: tuple[Decimal, ...]) -> int:
    """
    Given a value and a tuple of lower bounds, return the index of the highest lower bound that is less than or equal to the value.
    If the value is less than all lower bounds, return 0 (the first index).
    lower_bounds must be sorted in ascending order. This function is used to find the appropriate band index for a given value.
    """
    for i in range(len(lower_bounds) - 1, -1, -1):
        if value >= lower_bounds[i]:
            return i
    return 0
