import datetime
from dataclasses import dataclass

from django.db import transaction

from accounts.models import JudgeProfile, User
from accounts.roster import RowError
from exams.awards import Category
from exams.models import Certification, Cycle, Source


@dataclass(frozen=True)
class CategoryRow:
    sagf_id: str
    category: Category


@dataclass(frozen=True)
class CategoryChanges:
    add: list[CategoryRow]
    supercedes: list[tuple[CategoryRow, CategoryRow]]


class CategoryChanged(Exception):
    pass


def diff_categories(existing, incoming):
    existing_by_id = {row.sagf_id: row for row in existing}
    add = []
    supercedes = []

    for new_row in incoming:
        old_row = existing_by_id.get(new_row.sagf_id)
        if old_row is None:
            add.append(new_row)
        elif old_row.category != new_row.category:
            supercedes.append((old_row, new_row))

    return CategoryChanges(add=add, supercedes=supercedes)


def parse_categories(rows):
    parsed_rows = []
    errors = []
    seen: dict[str, int] = {}
    for line, row in enumerate(rows, start=2):
        sagf_id = row.get("sagf_id")
        try:
            category = Category(int(row.get("category")))
            if category == Category.FAIL:
                raise ValueError("Category 5 is invalid")
        except ValueError:
            errors.append(
                RowError(line=line, message=f"Invalid category: {row.get('category')}")
            )
            continue

        if sagf_id in seen:
            errors.append(
                RowError(
                    line=line,
                    message=f"Duplicate sagf_id: {sagf_id}, first seen on line {seen[sagf_id]}",
                )
            )
            continue
        seen[sagf_id] = line
        parsed_rows.append(CategoryRow(sagf_id=sagf_id, category=category))

    return parsed_rows if not errors else [], errors


def load_categories(cycle):
    latest_certifications = (
        Certification.objects.filter(cycle=cycle).order_by("pk").select_related("judge")
    )
    categories_by_judge = {}
    for cert in latest_certifications:
        categories_by_judge[cert.judge.sagf_id] = cert

    return [
        CategoryRow(sagf_id=sagf_id, category=Category(cert.category))
        for sagf_id, cert in categories_by_judge.items()
    ]


def apply_categories(changes, *, cycle, official, date):
    with transaction.atomic():
        for row in changes.add:
            profile, _created = JudgeProfile.objects.get_or_create(sagf_id=row.sagf_id)
            Certification.objects.create(
                judge=profile,
                cycle=cycle,
                certified_by=official,
                source=Source.IMPORTED,
                category=row.category,
                reason=f"Imported from the SAGF register, {date}",
            )
        for _old_row, new_row in changes.supercedes:
            profile, _created = JudgeProfile.objects.get_or_create(
                sagf_id=new_row.sagf_id
            )
            Certification.objects.create(
                judge=profile,
                cycle=cycle,
                certified_by=official,
                source=Source.IMPORTED,
                category=new_row.category,
                reason=f"Imported from the SAGF register, {date}",
            )


def confirm_categories(
    incoming: list[CategoryRow],
    *,
    cycle: Cycle,
    official: User,
    date: datetime.date,
    preview: CategoryChanges,
) -> None:
    if diff_categories(load_categories(cycle), incoming) != preview:
        raise CategoryChanged("Incoming categories do not match the preview")

    apply_categories(preview, cycle=cycle, official=official, date=date)
