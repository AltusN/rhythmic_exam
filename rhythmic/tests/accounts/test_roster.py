import json

import pytest
from django.db.utils import DataError

from accounts.models import RosterEntry
from accounts.roster import (
    RosterChanged,
    RosterChanges,
    RosterRow,
    RowError,
    apply_roster,
    confirm_roster,
    diff_roster,
    from_session,
    load_roster,
    parse_roster,
    to_session,
)


def test_a_valid_row_parses():
    rows = [{"sagf_id": "SAGF-00101", "email": "Judge@example.COm", "levels": "1;2"}]
    parsed, errors = parse_roster(rows)

    assert parsed == [
        RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1, 2))
    ]
    assert errors == []


def test_a_duplicate_sagf_id_is_an_error():
    rows = [
        {"sagf_id": "SAGF-00101", "email": "Judge@example.COm", "levels": "1;2"},
        {"sagf_id": "SAGF-00101", "email": "Another@example.COm", "levels": "3;4"},
        {"sagf_id": "SAGF-00101", "email": "Thirdrow@example.COm", "levels": "3;4"},
    ]
    parsed, errors = parse_roster(rows)

    assert parsed == []
    assert errors == [
        RowError(line=3, message="Duplicate sagf_id: SAGF-00101, first seen on line 2"),
        RowError(line=4, message="Duplicate sagf_id: SAGF-00101, first seen on line 2"),
    ]


def test_a_malformed_level_is_an_error():
    rows = [
        {"sagf_id": "SAGF-00101", "email": "Judge@example.COm", "levels": "1;two;three"}
    ]
    parsed, errors = parse_roster(rows)

    assert parsed == []
    assert errors == [
        RowError(line=2, message="Level 'two' is not a whole number"),
        RowError(line=2, message="Level 'three' is not a whole number"),
    ]


def test_a_malformed_row_still_claims_its_sagf_id():
    rows = [
        {"sagf_id": "SAGF-00101", "email": "a@example.com", "levels": "two"},
        {"sagf_id": "SAGF-00101", "email": "b@example.com", "levels": "1"},
    ]
    parsed, errors = parse_roster(rows)

    assert parsed == []
    assert errors == [
        RowError(line=2, message="Level 'two' is not a whole number"),
        RowError(line=3, message="Duplicate sagf_id: SAGF-00101, first seen on line 2"),
    ]


def test_a_new_judge_is_an_add():
    new = RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,))

    changes = diff_roster(existing=[], incoming=[new])

    assert changes == RosterChanges(add=[new], change=[], remove=[])


def test_a_missing_judge_is_removed():
    old = RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,))

    changes = diff_roster(existing=[old], incoming=[])

    assert changes == RosterChanges(add=[], change=[], remove=[old])


@pytest.mark.parametrize(
    "old,new",
    [
        (
            RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,)),
            RosterRow(sagf_id="SAGF-00101", email="new@example.com", levels=(1,)),
        ),
        (
            RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,)),
            RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1, 2)),
        ),
    ],
    ids=["email", "levels"],
)
def test_a_changed_field_is_a_change(old, new):
    changes = diff_roster(existing=[old], incoming=[new])

    assert changes == RosterChanges(add=[], change=[(old, new)], remove=[])


def test_an_unchanged_judge_is_not_a_change():
    old = RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,))
    new = RosterRow(sagf_id="SAGF-00101", email="judge@example.com", levels=(1,))

    assert diff_roster(existing=[old], incoming=[new]) == RosterChanges(
        add=[], change=[], remove=[]
    )


def test_the_diff_keeps_file_order():
    old_1 = RosterRow("SAGF-0001", "judge-0001@example.com", (1,))
    old_2 = RosterRow("SAGF-0002", "judge-0002@example.com", (1,))
    old_3 = RosterRow("SAGF-0003", "judge-0003@example.com", (1,))
    old_4 = RosterRow("SAGF-0004", "judge-0004@example.com", (1,))

    new_5 = RosterRow("SAGF-0005", "judge-0005@example.com", (1,))
    new_6 = RosterRow("SAGF-0006", "judge-0006@example.com", (1,))
    new_7 = RosterRow("SAGF-0007", "judge-0007@example.com", (1,))
    new_8 = RosterRow("SAGF-0008", "judge-0008@example.com", (1,))

    existing = [old_1, old_2, old_3, old_4]
    incoming = [new_5, new_6, new_7, new_8]

    assert diff_roster(existing=existing, incoming=incoming) == RosterChanges(
        add=[new_5, new_6, new_7, new_8],
        change=[],
        remove=[old_1, old_2, old_3, old_4],
    )


@pytest.mark.django_db
def test_apply_creates_an_added_judge():
    new = RosterRow(sagf_id="SAGF-0005", email="judge-0005@example.com", levels=(1, 2))

    apply_roster(RosterChanges(add=[new], change=[], remove=[]), year=2027)

    assert list(
        RosterEntry.objects.values_list("sagf_id", "email", "year", "levels")
    ) == [
        ("SAGF-0005", "judge-0005@example.com", 2027, [1, 2]),
    ]
    assert RosterEntry.history.filter(sagf_id="SAGF-0005").count() == 1


@pytest.mark.django_db
def test_apply_updates_a_changed_judge():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="old@example.com",
        year=2026,
        levels=[1],
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="old@example.com",
        year=2027,
        levels=[1],
    )
    old = RosterRow(sagf_id="SAGF-0001", email="old@example.com", levels=(1,))
    new = RosterRow(sagf_id="SAGF-0001", email="new@example.com", levels=(1, 2))

    apply_roster(RosterChanges(add=[], change=[(old, new)], remove=[]), year=2027)

    assert list(
        RosterEntry.objects.order_by("year").values_list(
            "sagf_id", "email", "year", "levels"
        )
    ) == [
        ("SAGF-0001", "old@example.com", 2026, [1]),
        ("SAGF-0001", "new@example.com", 2027, [1, 2]),
    ]


@pytest.mark.django_db
def test_apply_records_history():
    entry = RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="old@example.com", year=2027, levels=[1]
    )
    old = RosterRow(sagf_id="SAGF-0001", email="old@example.com", levels=(1,))
    new = RosterRow(sagf_id="SAGF-0001", email="new@example.com", levels=(1, 2))

    apply_roster(RosterChanges(add=[], change=[(old, new)], remove=[]), year=2027)

    assert entry.history.count() == 2


@pytest.mark.django_db(transaction=True)
def test_all_rows_are_applied_in_transaction():
    ok = RosterRow(sagf_id="SAGF-0001", email="a@example.com", levels=(1,))
    too_long = RosterRow(sagf_id="SAGF-" + "9" * 20, email="b@example.com", levels=(1,))

    changes = RosterChanges(add=[ok, too_long], change=[], remove=[])
    with pytest.raises(DataError):
        apply_roster(changes, year=2027)

    assert RosterEntry.objects.count() == 0
    assert RosterEntry.history.count() == 0


@pytest.mark.django_db
def test_apply_deletes_a_removed_judge():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2026, levels=[1]
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2027, levels=[1]
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0002", email="b@example.com", year=2027, levels=[1]
    )
    gone = RosterRow(sagf_id="SAGF-0001", email="a@example.com", levels=(1,))

    apply_roster(RosterChanges(add=[], change=[], remove=[gone]), year=2027)

    assert list(
        RosterEntry.objects.order_by("year", "sagf_id").values_list("sagf_id", "year")
    ) == [
        ("SAGF-0001", 2026),
        ("SAGF-0002", 2027),
    ]


@pytest.mark.django_db
def test_loading_a_roster_returns_roster_rows():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2026, levels=[1]
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0003", email="b@example.com", year=2027, levels=[1, 2]
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0002", email="c@example.com", year=2027, levels=[1]
    )

    roster = load_roster(year=2027)
    assert roster == [
        RosterRow(sagf_id="SAGF-0002", email="c@example.com", levels=(1,)),
        RosterRow(sagf_id="SAGF-0003", email="b@example.com", levels=(1, 2)),
    ]


@pytest.mark.django_db
def test_apply_refuses_a_stale_preview():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2027, levels=[1, 2]
    )

    incoming = [
        RosterRow(sagf_id="SAGF-0001", email="a@example.com", levels=(1,)),
        RosterRow(sagf_id="SAGF-0002", email="b@example.com", levels=(1,)),
    ]
    preview = diff_roster(load_roster(year=2027), incoming)

    # Simulate the roster changing after the preview was taken
    changed = RosterEntry.objects.get(sagf_id="SAGF-0001", year=2027)
    changed.email = "changed@example.com"
    changed.save()

    with pytest.raises(RosterChanged):
        confirm_roster(incoming, year=2027, preview=preview)

    assert list(RosterEntry.objects.values_list("sagf_id", "email", "levels")) == [
        ("SAGF-0001", "changed@example.com", [1, 2]),
    ]


@pytest.mark.django_db
def test_confirm_applies_a_fresh_roster():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2027, levels=[1, 2]
    )

    incoming = [
        RosterRow(sagf_id="SAGF-0001", email="a@example.com", levels=(1,)),
        RosterRow(sagf_id="SAGF-0002", email="b@example.com", levels=(1,)),
    ]
    preview = diff_roster(load_roster(year=2027), incoming)

    confirm_roster(incoming, year=2027, preview=preview)

    assert list(RosterEntry.objects.values_list("sagf_id", "email", "levels")) == [
        ("SAGF-0001", "a@example.com", [1]),
        ("SAGF-0002", "b@example.com", [1]),
    ]


def test_a_session_round_trip_keeps_the_preview_intact():
    incoming = [
        RosterRow("SAGF-0002", "b@example.com", (1,)),
        RosterRow("SAGF-0003", "c@example.com", (1, 2)),
    ]
    preview = RosterChanges(
        add=[RosterRow("SAGF-0002", "b@example.com", (1,))],
        change=[
            (
                RosterRow("SAGF-0003", "c@example.com", (1,)),
                RosterRow("SAGF-0003", "c@example.com", (1, 2)),
            )
        ],
        remove=[RosterRow("SAGF-0001", "a@example.com", (1,))],
    )

    session_data = json.loads(json.dumps(to_session(incoming, preview)))
    restored_incoming, restored_preview = from_session(session_data)

    assert restored_incoming == incoming
    assert restored_preview == preview


def test_a_sagf_id_too_long_is_an_error():
    rows = [
        {"sagf_id": "SAGF-" + "1" * 15, "email": "valid@example.com", "levels": "1"},
        {"sagf_id": "SAGF-" + "2" * 16, "email": "too-long@example.com", "levels": "2"},
    ]

    parsed, errors = parse_roster(rows)

    assert parsed == []
    assert errors == [RowError(line=3, message="SAGF ID must be at most 20 characters")]
