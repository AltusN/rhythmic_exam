from decimal import Decimal

from scoring.values import to_decimal


def test_it_works():
    assert to_decimal("1.0") == Decimal("1.0")
