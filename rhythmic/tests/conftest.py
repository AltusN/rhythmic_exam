from decimal import Decimal

import pytest

from scoring.types import BandRow, MarkingTable


@pytest.fixture()
def mark_table():
    row_1 = BandRow(
        expert_minimum=Decimal("0.0"),
        percentages=((Decimal("100"), Decimal("90"), Decimal("50"))),
    )

    row_2 = BandRow(
        expert_minimum=Decimal("2.0"),
        percentages=((Decimal("100"), Decimal("100"), Decimal("80"))),
    )

    return MarkingTable(
        difference_steps=(Decimal("0.0"), Decimal("0.1"), Decimal("0.2")),
        rows=(row_1, row_2),
    )
