from decimal import Decimal, InvalidOperation


class UnparseableAnswer(ValueError):
    """Exception raised when an answer cannot be parsed into a Decimal."""

    pass


def to_decimal(answer: str | Decimal | None) -> Decimal | None:
    """Convert a string answer to a Decimal, handling commas and slashes."""
    if answer is None or isinstance(answer, str) and answer.strip() == "":
        return None
    original_answer = answer  # Keep the original answer for error messages

    if isinstance(answer, str):
        # Replace comma with dot for decimal conversion
        answer = answer.replace(",", ".").replace("/", ".")
        answer = answer.strip()

    try:
        result = Decimal(answer)
    except InvalidOperation as e:
        raise UnparseableAnswer(f"Cannot parse answer: {original_answer}") from e

    if not result.is_finite():
        raise UnparseableAnswer(f"Answer is not finite: {original_answer}")

    return result
