from dataclasses import dataclass
from decimal import Decimal

from scoring.tables import floor_band_index


@dataclass(frozen=True)
class BandRow:
    expert_minimum: Decimal
    percentages: tuple[Decimal, ...]

@dataclass(frozen=True)
class MarkingTable:
    """
    Table of percentage marks indexed by expert-score and difference bands.

    `difference_steps` stores inclusive lower bounds for difference columns.
    `rows` stores `BandRow` entries in ascending expert_minimum order, where each
    row contains one percentage per difference column.

    Bands are half-open and open-ended at the top:
    - column i covers [difference_steps[i], difference_steps[i + 1])
    - the last column covers [difference_steps[-1], +inf)
    - row selection follows the same lower-bound floor rule on expert_minimum

    Values below the first lower bound fall back to the first row/column.
    """

    difference_steps: tuple[Decimal, ...]
    rows: tuple[BandRow, ...]

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("MarkingTable must have at least one row.")
        if not self.difference_steps:
            raise ValueError("MarkingTable must have at least one difference step.")
        # Validate that the rows are sorted by expert_minimum
        if sorted(self.rows, key=lambda row: row.expert_minimum) != list(self.rows):
            raise ValueError(
                "Rows must be sorted by expert_minimum in ascending order."
            )
        # validate the columns are sorted by difference_steps
        if sorted(self.difference_steps) != list(self.difference_steps):
            raise ValueError("Difference steps must be sorted in ascending order.")
        # Validate that the number of percentages in each row matches the number of difference steps
        for row in self.rows:
            if len(row.percentages) != len(self.difference_steps):
                raise ValueError(
                    f"Row with expert_minimum {row.expert_minimum} has {len(row.percentages)} percentages, "
                    f"but there are {len(self.difference_steps)} difference steps."
                )

    def lookup(self, *, expert: Decimal, difference: Decimal) -> Decimal:
        row_bounds = tuple(row.expert_minimum for row in self.rows)
        row_index = floor_band_index(value=expert, lower_bounds=row_bounds)

        column_index = floor_band_index(
            value=difference, lower_bounds=self.difference_steps
        )

        return self.rows[row_index].percentages[column_index]
