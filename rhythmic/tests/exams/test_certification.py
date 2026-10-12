from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from accounts.models import JudgeProfile
from exams.awards import Category
from exams.certification import (
    NotAPracticalSitting,
    ResultsIncomplete,
    SittingNotSubmitted,
    certify,
)
from exams.models import (
    CategoryRequirement,
    Certification,
    ComponentResult,
    Cycle,
    Dimension,
    Exam,
    ExamKind,
    Sitting,
    SittingItem,
    Source,
    Status,
)
from exams.tables import grade_bands_as_json
from scoring import GradeBand

# Excellent is 80% for Difficulty and 90% for Artistry and Execution.
DIFFICULTY_BANDS = (
    GradeBand("Fail", Decimal("0")),
    GradeBand("Pass", Decimal("50")),
    GradeBand("Good", Decimal("60")),
    GradeBand("Very Good", Decimal("70")),
    GradeBand("Excellent", Decimal("80")),
)
ARTISTRY_EXECUTION_BANDS = (
    GradeBand("Fail", Decimal("0")),
    GradeBand("Pass", Decimal("50")),
    GradeBand("Good", Decimal("65")),
    GradeBand("Very Good", Decimal("80")),
    GradeBand("Excellent", Decimal("90")),
)

DIMENSIONS = (Dimension.DIFFICULTY, Dimension.EXECUTION, Dimension.ARTISTRY)

CATEGORY_MINIMUMS = {
    1: ("Excellent", "Very Good", "Very Good"),
    2: ("Very Good", "Very Good", "Very Good"),
    3: ("Good", "Good", "Good"),
    4: ("Pass", "Pass", "Pass"),
}


@pytest.fixture
def submitted_practical(django_user_model, cycle):
    candidate = django_user_model.objects.create_user(
        username="practical-candidate", password="x"
    )
    JudgeProfile.objects.create(user=candidate, sagf_id="SAGF-0002")
    exam = Exam.objects.create(level=1, year=2026, kind=ExamKind.PRACTICAL)
    sitting = Sitting.objects.create(
        judge=candidate, exam=exam, status=Status.SUBMITTED
    )

    aspects = [
        ("DA", "85.00", "Excellent", grade_bands_as_json(DIFFICULTY_BANDS)),
        ("DB", "75.00", "Very Good", grade_bands_as_json(DIFFICULTY_BANDS)),
        ("AV", "82.00", "Very Good", grade_bands_as_json(ARTISTRY_EXECUTION_BANDS)),
        ("EX", "85.00", "Very Good", grade_bands_as_json(ARTISTRY_EXECUTION_BANDS)),
    ]
    for item in enumerate(aspects, start=1):
        index, (code, score, grade, bands) = item
        SittingItem.objects.create(
            component_name=f"Component {code}",
            sitting=sitting,
            component_aspect=code,
            grade_bands=bands,
            position=index,
            component_position=index,
            question_snapshot={},
            marking_scheme="NUMERIC",
            marking_key={},
        )
        ComponentResult.objects.create(
            component_name=f"Component {code}",
            sitting=sitting,
            aspect=code,
            percentage=Decimal(score),
            grade_name=grade,
            component_position=index,
        )

    for category, minimums in CATEGORY_MINIMUMS.items():
        for dimension, grade in zip(DIMENSIONS, minimums, strict=True):
            CategoryRequirement.objects.create(
                cycle=cycle,
                category=category,
                dimension=dimension,
                minimum_grade=grade,
            )

    return sitting


@pytest.fixture
def judge() -> JudgeProfile:
    return JudgeProfile.objects.create(user=None, sagf_id="SAGF-0001")


@pytest.fixture
def cycle() -> Cycle:
    return Cycle.objects.create(name="Cycle 1", first_year=2025, last_year=2028)


@pytest.fixture
def official(django_user_model):
    return django_user_model.objects.create_user(username="official", password="x")


@pytest.fixture
def sitting(django_user_model):
    candidate = django_user_model.objects.create_user(
        username="candidate", password="x"
    )
    exam = Exam.objects.create(level=1, year=2026, kind=ExamKind.PRACTICAL)
    return Sitting.objects.create(judge=candidate, exam=exam)


def _exam(judge, cycle, official, sitting):
    return {
        "judge": judge,
        "cycle": cycle,
        "sitting": sitting,
        "certified_by": official,
        "source": Source.EXAM,
        "category": 3,
        "examination_category": 3,
        "suggested_category": 3,
    }


def _imported(judge, cycle, official):
    return {
        "judge": judge,
        "cycle": cycle,
        "certified_by": official,
        "source": Source.IMPORTED,
        "category": 2,
        "reason": "Imported from the SAGF register",
    }


@pytest.mark.django_db
def test_an_exam_certification_needs_a_sitting(judge, cycle, official, sitting):

    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(
            **{**_exam(judge, cycle, official, sitting), "sitting": None}
        )


@pytest.mark.django_db
def test_an_imported_certification_needs_a_reason(judge, cycle, official):
    # valid rows save
    Certification.objects.create(**_imported(judge, cycle, official))
    # missing reason raises an IntegrityError
    data = _imported(judge, cycle, official)
    data["reason"] = ""
    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(**data)


@pytest.mark.parametrize(
    "column",
    ["examination_category", "suggested_category", "floor", "cap"],
    ids=["examination", "suggested", "floor", "cap"],
)
@pytest.mark.django_db
def test_an_imported_certification_computes_nothing(judge, cycle, official, column):
    data = _imported(judge, cycle, official)
    data[column] = 2
    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(**data)


@pytest.mark.django_db
def test_a_valid_exam_certification_saves(judge, cycle, official, sitting):
    data = _exam(judge, cycle, official, sitting)
    Certification.objects.create(**data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "column",
    ["examination_category", "suggested_category"],
    ids=["examination", "suggested"],
)
def test_an_exam_certification_needs_its_computed_values(
    judge, cycle, official, sitting, column
):
    data = _exam(judge, cycle, official, sitting)
    data[column] = None
    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(**data)


@pytest.mark.django_db
def test_departing_from_the_suggestion_needs_a_reason(judge, cycle, official, sitting):
    data = _exam(judge, cycle, official, sitting)
    data["suggested_category"] = 2
    data["category"] = 3
    data["reason"] = ""
    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(**data)

    data["reason"] = "Departing from the suggestion"
    Certification.objects.create(**data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "column", ["category", "examination_category", "suggested_category", "floor", "cap"]
)
@pytest.mark.parametrize("value", [0, 6])
def test_a_category_outside_one_to_five_is_refused(
    judge, cycle, official, sitting, column, value
):
    data = _exam(judge, cycle, official, sitting)
    data[column] = value
    data["reason"] = "Category out of range"
    with pytest.raises(IntegrityError), transaction.atomic():
        Certification.objects.create(**data)


@pytest.mark.django_db
def test_an_unsubmitted_sitting_cannot_be_certified(judge, cycle, official, sitting):
    with pytest.raises(SittingNotSubmitted):
        certify(sitting, official=official, category=Category.THREE)

    assert not Certification.objects.filter(sitting=sitting).exists()


@pytest.mark.django_db
def test_certify_reads_the_status_from_the_row(official, sitting):
    sitting.status = Status.SUBMITTED  # in memory only: the row still says PENDING
    with pytest.raises(SittingNotSubmitted):
        certify(sitting, official=official, category=Category.THREE)


@pytest.mark.django_db
def test_a_theory_sitting_cannot_be_certified(django_user_model, official):
    candidate = django_user_model.objects.create_user(
        username="theory-candidate",
        password="test-password",
    )
    exam = Exam.objects.create(level=1, year=2026, kind=ExamKind.THEORY)
    theory_sitting = Sitting.objects.create(
        judge=candidate,
        exam=exam,
        status=Status.SUBMITTED,
    )

    with pytest.raises(NotAPracticalSitting):
        certify(theory_sitting, official=official, category=Category.THREE)


@pytest.mark.django_db
def test_a_sitting_missing_a_result_cannot_be_certified(official, sitting):
    Sitting.objects.filter(pk=sitting.pk).update(status=Status.SUBMITTED)

    for position, aspect in enumerate(("DA", "DB", "EX"), start=1):
        ComponentResult.objects.create(
            sitting=sitting,
            component_name=aspect,
            component_position=position,
            aspect=aspect,
            percentage=Decimal("75.00"),
            grade_name="Good",
        )

    # Confirm the setup leaves exactly AV missing.
    assert list(
        sitting.results.order_by("component_position").values_list("aspect", flat=True)
    ) == ["DA", "DB", "EX"]

    with pytest.raises(ResultsIncomplete, match="AV"):
        certify(sitting, official=official, category=Category.THREE)


@pytest.mark.django_db
def test_the_submitted_practical_fixture_is_complete(submitted_practical):
    assert sorted(submitted_practical.results.values_list("aspect", flat=True)) == [
        "AV",
        "DA",
        "DB",
        "EX",
    ]
    assert (
        submitted_practical.items.count() == 4
    )  # Assuming a complete practical sitting has 4 results
    assert CategoryRequirement.objects.count() == 12


@pytest.mark.django_db
def test_certifying_stores_what_the_official_saw(official, submitted_practical):
    certify(submitted_practical, official=official, category=Category.THREE)

    cert = Certification.objects.get(sitting=submitted_practical)

    assert cert.examination_category == 1
    assert cert.cap == 3
    assert cert.floor is None
    assert cert.suggested_category == 3
    assert cert.category == 3
    assert cert.source == Source.EXAM


@pytest.mark.django_db
def test_certifying_marks_the_sitting_certified(official, submitted_practical):
    certify(submitted_practical, official=official, category=Category.THREE)

    submitted_practical.refresh_from_db()
    assert submitted_practical.status == Status.CERTIFIED


@pytest.mark.django_db
def test_a_previous_category_sets_a_floor(official, submitted_practical):
    previous = Cycle.objects.create(
        name="Previous Cycle", first_year=2021, last_year=2024
    )
    profile = submitted_practical.judge.judge_profile

    Certification.objects.create(
        judge=profile,
        cycle=previous,
        source=Source.IMPORTED,
        category=1,
        certified_by=official,
        reason="barnicals",
    )

    certify(submitted_practical, official=official, category=Category.ONE)

    cert = Certification.objects.get(sitting=submitted_practical)
    assert (cert.cap, cert.floor, cert.suggested_category) == (None, 3, 1)


@pytest.mark.django_db
def test_history_is_the_judge_s_own(official, submitted_practical, judge):
    previous = Cycle.objects.create(
        name="Previous Cycle", first_year=2021, last_year=2024
    )

    Certification.objects.create(
        judge=judge,
        cycle=previous,
        source=Source.IMPORTED,
        category=1,
        certified_by=official,
        reason="barnicals",
    )

    certify(
        submitted_practical,
        official=official,
        category=Category.THREE,
        reason="Following the first-cycle cap",
    )

    cert = Certification.objects.get(sitting=submitted_practical)
    assert (cert.cap, cert.floor, cert.suggested_category) == (3, None, 3)


@pytest.mark.django_db
def test_the_latest_previous_category_counts(official, submitted_practical):
    previous = Cycle.objects.create(
        name="Recent Cycle", first_year=2021, last_year=2024
    )

    profile = submitted_practical.judge.judge_profile

    Certification.objects.create(
        judge=profile,
        cycle=previous,
        source=Source.IMPORTED,
        category=1,
        certified_by=official,
        reason="barnicals",
    )

    Certification.objects.create(
        judge=profile,
        cycle=previous,
        source=Source.IMPORTED,
        category=4,
        certified_by=official,
        reason="barnicals",
    )

    certify(submitted_practical, official=official, category=Category.ONE)

    cert = Certification.objects.get(sitting=submitted_practical)
    assert (cert.cap, cert.floor, cert.suggested_category) == (None, None, 1)


@pytest.mark.django_db
def test_a_departure_stores_its_reason_trimmed(official, submitted_practical):
    reason = "  some reason with spaces  "
    certify(
        submitted_practical,
        official=official,
        category=Category.ONE,
        reason=reason,
    )
    cert = Certification.objects.get(sitting=submitted_practical)
    assert (cert.category, cert.reason) == (1, "some reason with spaces")
