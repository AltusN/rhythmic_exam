from dataclasses import dataclass
from typing import Any

from django.db import transaction

from .models import RosterEntry


@dataclass(frozen=True)
class RowError:
    line: int
    message: str


@dataclass(frozen=True)
class RosterRow:
    sagf_id: str
    email: str
    levels: tuple[int, ...]


@dataclass(frozen=True)
class RosterChanges:
    add: list[RosterRow]
    change: list[tuple[RosterRow, RosterRow]]
    remove: list[RosterRow]


class RosterChanged(Exception):
    """The roster moved after the preview was taken"""


def _row_to_dict(row: RosterRow) -> dict[str, object]:
    return {"sagf_id": row.sagf_id, "email": row.email, "levels": row.levels}


def _row_from_dict(data: dict[str, Any]) -> RosterRow:
    return RosterRow(
        sagf_id=data["sagf_id"],
        email=data["email"],
        levels=tuple(data["levels"]),
    )


def parse_roster(rows: list[dict[str, str]]) -> tuple[list[RosterRow], list[RowError]]:
    MAX_SAGF_ID = RosterEntry._meta.get_field("sagf_id").max_length
    parsed = []
    errors = []
    seen: dict[str, int] = {}  # Maps sagf_id to line number
    for line, row in enumerate(rows, start=2):
        sagf_id = row["sagf_id"]
        if len(sagf_id) > MAX_SAGF_ID:
            errors.append(
                RowError(
                    line=line,
                    message=f"SAGF ID must be at most {MAX_SAGF_ID} characters",
                )
            )
        if sagf_id in seen:
            errors.append(
                RowError(
                    line=line,
                    message=f"Duplicate sagf_id: {sagf_id}, first seen on line {seen[sagf_id]}",
                )
            )
            continue
        seen[sagf_id] = line
        levels = []
        for piece in row["levels"].split(";"):
            try:
                levels.append(int(piece))
            except ValueError:
                errors.append(
                    RowError(
                        line=line, message=f"Level {piece!r} is not a whole number"
                    )
                )

        parsed.append(
            RosterRow(sagf_id=sagf_id, email=row["email"].lower(), levels=tuple(levels))
        )
    return ([] if errors else parsed, errors)


def diff_roster(existing: list[RosterRow], incoming: list[RosterRow]) -> RosterChanges:
    incoming_ids = {row.sagf_id for row in incoming}
    existing_by_id = {row.sagf_id: row for row in existing}

    added = [row for row in incoming if row.sagf_id not in existing_by_id]
    remove = [row for row in existing if row.sagf_id not in incoming_ids]
    change = [
        (existing_by_id[row.sagf_id], row)
        for row in incoming
        if row.sagf_id in existing_by_id and existing_by_id[row.sagf_id] != row
    ]

    return RosterChanges(add=added, change=change, remove=remove)


def apply_roster(changes: RosterChanges, *, year: int) -> None:
    with transaction.atomic():
        for row in changes.add:
            RosterEntry.objects.create(
                sagf_id=row.sagf_id,
                email=row.email,
                year=year,
                levels=row.levels,
            )

        for _, row in changes.change:
            entry = RosterEntry.objects.get(sagf_id=row.sagf_id, year=year)
            entry.email = row.email
            entry.levels = row.levels
            entry.save()

        for row in changes.remove:
            entry = RosterEntry.objects.get(sagf_id=row.sagf_id, year=year)
            entry.delete()


def load_roster(year: int) -> list[RosterRow]:
    rows = RosterEntry.objects.filter(year=year).values("sagf_id", "email", "levels")
    return [
        RosterRow(
            sagf_id=row["sagf_id"],
            email=row["email"],
            levels=tuple(row["levels"]),
        )
        for row in rows
    ]


def confirm_roster(
    incoming: list[RosterRow], *, year: int, preview: RosterChanges
) -> None:
    # Guards the gap between preview and confirm (an official reading the page).
    # Not a lock: an edit committed between load_roster and apply_roster still lands.

    if diff_roster(load_roster(year=year), incoming) != preview:
        raise RosterChanged

    apply_roster(preview, year=year)


def to_session(incoming: list[RosterRow], preview: RosterChanges) -> dict:
    return {
        "incoming": [_row_to_dict(row) for row in incoming],
        "preview": {
            "add": [_row_to_dict(row) for row in preview.add],
            "change": [
                (
                    _row_to_dict(old),
                    _row_to_dict(new),
                )
                for old, new in preview.change
            ],
            "remove": [_row_to_dict(row) for row in preview.remove],
        },
    }


def from_session(data: dict) -> tuple[list[RosterRow], RosterChanges]:
    incoming = [_row_from_dict(row) for row in data["incoming"]]
    preview = RosterChanges(
        add=[_row_from_dict(row) for row in data["preview"]["add"]],
        change=[
            (
                _row_from_dict(old),
                _row_from_dict(new),
            )
            for old, new in data["preview"]["change"]
        ],
        remove=[_row_from_dict(row) for row in data["preview"]["remove"]],
    )

    return incoming, preview
