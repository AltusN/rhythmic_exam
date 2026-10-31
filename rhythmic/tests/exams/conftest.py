import pytest

from accounts.models import JudgeProfile
from exams.models import Cycle, Exam, ExamKind, Sitting


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
