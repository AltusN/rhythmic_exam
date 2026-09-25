import pytest

from exams.eligibility import Refusal, refusals

# No django_db marker anywhere in this file: the rule is a pure function. A test
# here that needs the database means a query leaked into eligibility.py.

ELIGIBLE = {
    "roster_levels": [1, 2],
    "exam_level": 2,
    "prior_practical_sittings": 0,
    "has_open_sitting": False,
    "exam_is_practical": True,
}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, []),
        ({"roster_levels": None}, [Refusal.NOT_ON_ROSTER]),
        # An entry permitting nothing is not the same as no entry: absence is not
        # an empty value.
        ({"roster_levels": []}, [Refusal.LEVEL_NOT_PERMITTED]),
        ({"roster_levels": [1]}, [Refusal.LEVEL_NOT_PERMITTED]),
        # One prior sitting and two together pin the section 2.7 boundary: the
        # first attempt plus one retest, then no more.
        ({"prior_practical_sittings": 1}, []),
        ({"prior_practical_sittings": 2}, [Refusal.RETEST_USED]),
        ({"prior_practical_sittings": 5, "exam_is_practical": False}, []),
        ({"has_open_sitting": True}, [Refusal.ALREADY_ENROLLED]),
        (
            {
                "roster_levels": None,
                "prior_practical_sittings": 2,
                "has_open_sitting": True,
            },
            [Refusal.NOT_ON_ROSTER, Refusal.RETEST_USED, Refusal.ALREADY_ENROLLED],
        ),
    ],
    ids=[
        "eligible",
        "not-on-roster",
        "empty-roster-entry",
        "level-not-permitted",
        "first-retest-allowed",
        "second-retest-refused",
        "theory-has-no-retest-limit",
        "already-enrolled",
        "every-refusal-at-once",
    ],
)
def test_refusals(changes, expected):
    # The list, in declaration order -- an official deciding whether to override
    # needs every reason, not the first.
    assert refusals(**{**ELIGIBLE, **changes}) == expected
