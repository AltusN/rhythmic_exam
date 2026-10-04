import pytest
from django.db import IntegrityError, transaction

from accounts.models import JudgeProfile
from exams.models import Certification, Cycle, Exam, ExamKind, Sitting, Source


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
