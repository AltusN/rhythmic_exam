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


@pytest.mark.parametrize(
    "expert, difference, percentage",
    [
        (Decimal("0.0"), Decimal("0.0"), Decimal("100")),
        (Decimal("0.0"), Decimal("0.1"), Decimal("90")),
        (Decimal("0.0"), Decimal("0.15"), Decimal("90")),
        (Decimal("0.0"), Decimal("0.07"), Decimal("100")),
        (Decimal("0.0"), Decimal("5.0"), Decimal("50")),
        (Decimal("2.0"), Decimal("0.1"), Decimal("100")),
        (Decimal("3.5"), Decimal("0.1"), Decimal("100")),
        (Decimal("1.9"), Decimal("0.1"), Decimal("90")),
    ],
    ids=[
        "exact first row",
        "exact column boundary",
        "floors into 0.1 band",
        "F4 regression - must not raise",
        "above top column - uses last",
        "second row selected",
        "above top row - uses last",
        "just below second row - uses first row",
    ],
)
def test_lookup_percentage(mark_table, expert, difference, percentage):
    result = mark_table.lookup(expert=expert, difference=difference)
    assert result == percentage


def test_post_init_rejects_empty_rows():
    with pytest.raises(ValueError, match="at least one row"):
        MarkingTable(difference_steps=(Decimal("0.0"),), rows=())


def test_post_init_rejects_empty_difference_steps():
    with pytest.raises(ValueError, match="at least one difference step"):
        MarkingTable(
            difference_steps=(),
            rows=(
                BandRow(expert_minimum=Decimal("0.0"), percentages=(Decimal("100"),)),
            ),
        )


def test_post_init_rejects_unsorted_rows():
    row_1 = BandRow(
        expert_minimum=Decimal("2.0"),
        percentages=((Decimal("100"), Decimal("90"), Decimal("50"))),
    )

    row_2 = BandRow(
        expert_minimum=Decimal("0.0"),
        percentages=((Decimal("100"), Decimal("100"), Decimal("80"))),
    )

    with pytest.raises(ValueError, match="sorted.*expert_minimum"):
        MarkingTable(
            difference_steps=(Decimal("0.0"), Decimal("0.1"), Decimal("0.2")),
            rows=(row_1, row_2),
        )


def test_post_init_rejects_mismatched_percentages():
    row_1 = BandRow(
        expert_minimum=Decimal("0.0"),
        percentages=((Decimal("100"), Decimal("90"))),  # Only 2 percentages
    )

    with pytest.raises(ValueError, match="percentages.*difference steps"):
        MarkingTable(
            difference_steps=(
                Decimal("0.0"),
                Decimal("0.1"),
                Decimal("0.2"),
            ),  # 3 difference steps
            rows=(row_1,),
        )


def test_post_init_rejects_unsorted_difference_steps():
    row_1 = BandRow(
        expert_minimum=Decimal("0.0"),
        percentages=((Decimal("100"), Decimal("90"), Decimal("50"))),
    )

    with pytest.raises(ValueError, match="Difference steps.*sorted"):
        MarkingTable(
            difference_steps=(
                Decimal("0.2"),
                Decimal("0.1"),
                Decimal("0.0"),
            ),  # Unsorted
            rows=(row_1,),
        )
