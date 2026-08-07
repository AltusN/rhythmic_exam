from decimal import Decimal

from scoring.types import BandRow, MarkingTable


def sagf_legacy_table() -> MarkingTable:
    difference_steps = tuple(Decimal(i) * Decimal("0.05") for i in range(21))
    percentages = reversed(tuple(Decimal(i) * Decimal("5") for i in range(21)))
    row = BandRow(expert_minimum=Decimal("0"), percentages=tuple(percentages))

    return MarkingTable(difference_steps=difference_steps, rows=(row,))
