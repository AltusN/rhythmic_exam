from datetime import date

import pytest

import exams.category_import as category_import
from accounts.models import JudgeProfile
from exams.awards import Category
from exams.category_import import (
    CategoryChanges,
    CategoryRow,
    diff_categories,
    load_categories,
    parse_categories,
)
from exams.models import Certification, Cycle, Source


def test_category_five_is_an_error():
    lines = [{"sagf_id": "T001", "category": "5"}]

    rows, errors = parse_categories(lines)
    assert rows == []
    assert len(errors) == 1


def test_a_valid_row_parses():
    lines = [{"sagf_id": "T001", "category": "2"}]

    rows, errors = parse_categories(lines)
    assert rows == [CategoryRow(sagf_id="T001", category=Category.TWO)]
    assert errors == []


def test_a_malformed_category_is_an_error():
    lines = [{"sagf_id": "T001", "category": "x"}]

    rows, errors = parse_categories(lines)
    assert rows == []
    assert len(errors) == 1


def test_a_category_outside_the_scale_is_an_error():
    lines = [{"sagf_id": "T001", "category": "6"}]

    rows, errors = parse_categories(lines)
    assert rows == []
    assert len(errors) == 1


def test_one_bad_row_rejects_the_whole_file():
    lines = [{"sagf_id": "T001", "category": "2"}, {"sagf_id": "T002", "category": "x"}]

    rows, errors = parse_categories(lines)
    assert rows == []
    assert len(errors) == 1
    assert errors[0].line == 3


def test_a_duplicate_sagf_id_is_an_error():
    lines = [{"sagf_id": "T001", "category": "2"}, {"sagf_id": "T001", "category": "1"}]

    rows, errors = parse_categories(lines)
    assert rows == []
    assert len(errors) == 1
    assert errors[0].line == 3


def test_the_diff_finds_adds_and_supercedes():
    existing = [
        CategoryRow(sagf_id="T001", category=Category.TWO),
        CategoryRow(sagf_id="T002", category=Category.THREE),
    ]
    incoming = [
        CategoryRow(sagf_id="T001", category=Category.TWO),
        CategoryRow(sagf_id="T002", category=Category.ONE),
        CategoryRow(sagf_id="T003", category=Category.FOUR),
    ]

    assert diff_categories(existing, incoming) == CategoryChanges(
        add=[CategoryRow(sagf_id="T003", category=Category.FOUR)],
        supercedes=[
            (
                CategoryRow(sagf_id="T002", category=Category.THREE),
                CategoryRow(sagf_id="T002", category=Category.ONE),
            )
        ],
    )


@pytest.mark.django_db
def test_load_returns_the_latest_certification_in_the_cycle(judge, cycle, official):
    Certification.objects.create(
        judge=judge,
        cycle=cycle,
        certified_by=official,
        source=Source.IMPORTED,
        category=Category.TWO,
        reason="reason for row 1",
    )
    Certification.objects.create(
        judge=judge,
        cycle=cycle,
        certified_by=official,
        source=Source.IMPORTED,
        category=Category.ONE,
        reason="reason for row 2",
    )

    loaded = load_categories(cycle)
    assert loaded == [CategoryRow(sagf_id=judge.sagf_id, category=Category.ONE)]


@pytest.mark.django_db
def test_load_ignores_other_cycles(judge, cycle, official):
    previous_cycle = Cycle.objects.create(
        name="Cycle 0", first_year=2021, last_year=2024
    )

    Certification.objects.create(
        judge=judge,
        cycle=previous_cycle,
        certified_by=official,
        source=Source.IMPORTED,
        category=Category.TWO,
        reason="reason for another cycle",
    )

    loaded = load_categories(cycle)
    assert loaded == []


@pytest.mark.django_db
def test_load_includes_exam_certifications(judge, cycle, official, sitting):
    Certification.objects.create(
        judge=judge,
        cycle=cycle,
        certified_by=official,
        source=Source.EXAM,
        category=Category.TWO,
        reason="reason for exam certification",
        sitting=sitting,
        examination_category=Category.TWO,
        suggested_category=Category.TWO,
    )

    loaded = load_categories(cycle)
    assert loaded == [CategoryRow(sagf_id=judge.sagf_id, category=Category.TWO)]


@pytest.mark.django_db
def test_an_import_creates_a_judge_without_a_login(cycle, official):
    changes = CategoryChanges(
        add=[CategoryRow(sagf_id="T100", category=Category.TWO)],
        supercedes=[],
    )

    category_import.apply_categories(
        changes,
        cycle=cycle,
        official=official,
        date=date(2026, 10, 31),
    )

    profile = JudgeProfile.objects.get(sagf_id="T100")
    assert profile.user_id is None
    assert list(
        profile.certifications.values_list(
            "source", "category", "cycle_id", "certified_by_id", "reason"
        )
    ) == [
        (
            "IMPORTED",
            2,
            cycle.pk,
            official.pk,
            "Imported from the SAGF register, 2026-10-31",
        )
    ]


@pytest.mark.django_db
def test_a_different_category_supersedes(judge, cycle, official):
    Certification.objects.create(
        judge=judge,
        cycle=cycle,
        certified_by=official,
        source=Source.IMPORTED,
        category=Category.TWO,
        reason="reason for row 1",
    )
    changes = CategoryChanges(
        add=[],
        supercedes=[
            (
                CategoryRow(judge.sagf_id, Category.TWO),
                CategoryRow(judge.sagf_id, Category.ONE),
            )
        ],
    )

    category_import.apply_categories(
        changes,
        cycle=cycle,
        official=official,
        date=date(2026, 10, 31),
    )

    assert list(
        judge.certifications.order_by("pk").values_list("category", flat=True)
    ) == [2, 1]


@pytest.mark.django_db
def test_confirm_refuses_a_stale_preview(judge, cycle, official):
    incoming = [CategoryRow(sagf_id=judge.sagf_id, category=Category.TWO)]
    preview = CategoryChanges(add=[], supercedes=[])

    with pytest.raises(category_import.CategoryChanged):
        category_import.confirm_categories(
            incoming,
            cycle=cycle,
            official=official,
            date=date(2026, 10, 31),
            preview=preview,
        )

    assert (
        list(judge.certifications.order_by("pk").values_list("category", flat=True))
        == []
    )


@pytest.mark.django_db
def test_confirm_applies_a_fresh_preview(judge, cycle, official):
    Certification.objects.create(
        judge=judge,
        cycle=cycle,
        certified_by=official,
        source=Source.IMPORTED,
        category=Category.TWO,
        reason="reason for row 1",
    )
    incoming = [CategoryRow(sagf_id=judge.sagf_id, category=Category.ONE)]
    preview = diff_categories(load_categories(cycle), incoming)
    category_import.confirm_categories(
        incoming,
        cycle=cycle,
        official=official,
        date=date(2026, 10, 31),
        preview=preview,
    )

    assert list(
        judge.certifications.order_by("pk").values_list("category", flat=True)
    ) == [2, 1]
