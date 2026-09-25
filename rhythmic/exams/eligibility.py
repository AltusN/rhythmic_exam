"""Whether a judge may enrol for an exam. Pure: plain values in, no model, no query.

`exams/enrolment.py` loads the inputs and records the outcome; this module only
decides. It imports nothing from Django, like `scoring/`, so its tests need no
database -- a test that does means a query has leaked in here.
"""

import enum
from collections.abc import Sequence

# General Judges' Rules section 2.7: one retest per judge per cycle, so the first
# attempt plus one retest.
PRACTICAL_SITTINGS_PER_CYCLE = 2


class Refusal(enum.Enum):
    NOT_ON_ROSTER = "Not on this year's roster"
    LEVEL_NOT_PERMITTED = "The roster does not permit this level"
    RETEST_USED = "The one retest this cycle has been used"
    ALREADY_ENROLLED = "Already enrolled for this exam"


def refusals(
    *,
    roster_levels: Sequence[int] | None,
    exam_level: int,
    prior_practical_sittings: int,
    has_open_sitting: bool,
    exam_is_practical: bool,
) -> list[Refusal]:
    """Every reason this enrolment breaks a rule, in declaration order.

    `roster_levels` is None when the judge has no roster entry for the exam's year
    and an empty sequence when the entry permits nothing -- different refusals, so
    never test it for truthiness.

    Collects all reasons rather than stopping at the first: an official deciding
    whether to override needs the whole list.
    """
    found = []
    if roster_levels is None:
        found.append(Refusal.NOT_ON_ROSTER)
    elif exam_level not in roster_levels:
        found.append(Refusal.LEVEL_NOT_PERMITTED)
    # Theory decides nothing, so a retest limit on it would guard nothing.
    if exam_is_practical and prior_practical_sittings >= PRACTICAL_SITTINGS_PER_CYCLE:
        found.append(Refusal.RETEST_USED)
    if has_open_sitting:
        found.append(Refusal.ALREADY_ENROLLED)
    return found
