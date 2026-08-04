from decimal import Decimal

from scoring.types import MarkingTable
from scoring.values import to_decimal


def mark_choice(response: str | None, correct_option: str) -> Decimal:
    return Decimal("100") if response == correct_option else Decimal("0")


def mark_numeric(
    response: str | None, expert_score: Decimal, table: MarkingTable
) -> Decimal:
    response_decimal = to_decimal(response)
    if response_decimal is None:
        return Decimal("0")

    return table.lookup(
        expert=expert_score,
        difference=abs(response_decimal - expert_score),
    )
