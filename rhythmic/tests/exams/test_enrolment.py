import pytest
from django.db import IntegrityError, transaction

from accounts.models import JudgeProfile, RosterEntry
from exams.eligibility import Refusal
from exams.enrolment import EnrolmentRefused, JudgeHasNoProfile, enrol
from exams.models import Cycle, Exam, ExamKind, Sitting, Status


@pytest.fixture
def cycles():
    Cycle.objects.create(name="XVI", first_year=2025, last_year=2028)
    Cycle.objects.create(name="XVII", first_year=2029, last_year=2032)


@pytest.fixture
def official(django_user_model):
    return django_user_model.objects.create_user(username="official", password="x")


@pytest.fixture
def judge(django_user_model):
    user = django_user_model.objects.create_user(username="judge", password="x")
    JudgeProfile.objects.create(user=user, sagf_id="SAGF-0001")
    return user


def _practical(year):
    return Exam.objects.create(level=1, year=year, kind=ExamKind.PRACTICAL)


def _on_roster(year, levels=(1,)):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="judge@example.com", year=year, levels=list(levels)
    )


@pytest.mark.django_db
def test_an_eligible_judge_is_enrolled(cycles, judge, official):
    exam = _practical(2026)
    _on_roster(2026)

    sitting = enrol(judge, exam, official=official)

    stored = Sitting.objects.get(pk=sitting.pk)
    assert (stored.judge_id, stored.exam_id, stored.status) == (
        judge.pk,
        exam.pk,
        Status.PENDING,
    )
    assert stored.override_by_id is None


@pytest.mark.django_db
def test_an_ineligible_judge_is_refused_with_reasons(cycles, judge, official):
    # Same fixtures as the eligible test above, minus the roster entry: that test is
    # the control showing enrol() does create a sitting when nothing is wrong.
    exam = _practical(2026)

    with pytest.raises(EnrolmentRefused) as refused:
        enrol(judge, exam, official=official)

    assert refused.value.refusals == [Refusal.NOT_ON_ROSTER]
    assert Sitting.objects.count() == 0


@pytest.mark.django_db
def test_an_override_records_who_and_why(cycles, judge, official):
    exam = _practical(2026)

    sitting = enrol(
        judge, exam, official=official, override_reason="  Medical certificate  "
    )

    stored = Sitting.objects.get(pk=sitting.pk)
    assert stored.override_by_id == official.pk
    assert stored.override_reason == "Medical certificate"


@pytest.mark.django_db
def test_a_blank_override_is_no_override(cycles, judge, official):
    exam = _practical(2026)

    with pytest.raises(EnrolmentRefused):
        enrol(judge, exam, official=official, override_reason="   ")


@pytest.mark.django_db
def test_an_eligible_enrolment_records_no_override(cycles, judge, official):
    # A reason given when nothing needed overriding is noise in the audit trail.
    exam = _practical(2026)
    _on_roster(2026)

    sitting = enrol(judge, exam, official=official, override_reason="Just in case")

    stored = Sitting.objects.get(pk=sitting.pk)
    assert (stored.override_by_id, stored.override_reason) == (None, "")


@pytest.mark.django_db
def test_a_judge_without_a_profile_cannot_be_enrolled(
    cycles, django_user_model, official
):
    stranger = django_user_model.objects.create_user(username="stranger", password="x")

    # Not a refusal: with no sagf_id there is nothing to check, so no override helps.
    with pytest.raises(JudgeHasNoProfile):
        enrol(stranger, _practical(2026), official=official, override_reason="Please")


@pytest.mark.django_db
def test_the_retest_limit_counts_across_the_cycle(cycles, judge, official):
    # Two practical sittings on DIFFERENT exams in the same cycle. Counting by
    # exam would see none for 2028 and let a third attempt through.
    for year in (2025, 2027, 2028, 2029):
        _on_roster(year)
    Sitting.objects.create(judge=judge, exam=_practical(2025))
    Sitting.objects.create(judge=judge, exam=_practical(2027))

    with pytest.raises(EnrolmentRefused) as refused:
        enrol(judge, _practical(2028), official=official)
    assert refused.value.refusals == [Refusal.RETEST_USED]

    # The next cycle starts the count again.
    assert enrol(judge, _practical(2029), official=official).exam.year == 2029


@pytest.mark.django_db
def test_candidate_numbers_differ_within_an_exam(
    cycles, judge, official, django_user_model
):
    # Pins that the default is generated per sitting: a constant default would make
    # the second enrolment collide with the first on the unique constraint.
    other = django_user_model.objects.create_user(username="other", password="x")
    JudgeProfile.objects.create(user=other, sagf_id="SAGF-0002")
    exam = _practical(2026)
    _on_roster(2026)
    RosterEntry.objects.create(
        sagf_id="SAGF-0002", email="other@example.com", year=2026, levels=[1]
    )

    first = enrol(judge, exam, official=official)
    second = enrol(other, exam, official=official)

    assert first.candidate_number != second.candidate_number


@pytest.mark.django_db
def test_a_candidate_number_is_unique_within_an_exam(judge, django_user_model):
    # Two DIFFERENT judges: the number is anonymous, so it must not repeat across
    # candidates. With one judge, a key that also included the judge would still
    # refuse the duplicate and the test could not tell the two keys apart.
    other = django_user_model.objects.create_user(username="other", password="x")
    exam = _practical(2026)
    Sitting.objects.create(judge=judge, exam=exam, candidate_number="ABCD1234")

    with pytest.raises(IntegrityError), transaction.atomic():
        Sitting.objects.create(judge=other, exam=exam, candidate_number="ABCD1234")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("with_official", "reason"),
    [(False, "A reason"), (True, "")],
    ids=["reason-without-official", "official-without-reason"],
)
def test_an_override_is_both_halves_or_neither(judge, official, with_official, reason):
    exam = _practical(2026)

    with pytest.raises(IntegrityError), transaction.atomic():
        Sitting.objects.create(
            judge=judge,
            exam=exam,
            override_by=official if with_official else None,
            override_reason=reason,
        )


@pytest.mark.django_db
def test_an_open_sitting_blocks_a_second_enrolment(cycles, judge, official):
    exam = _practical(2026)
    _on_roster(2026)
    enrol(judge, exam, official=official)

    with pytest.raises(EnrolmentRefused) as refused:
        enrol(judge, exam, official=official)

    assert refused.value.refusals == [Refusal.ALREADY_ENROLLED]


@pytest.mark.django_db
def test_a_submitted_sitting_does_not_block_a_retest(cycles, judge, official):
    # A judge who fails may retake the same exam: only a PENDING or IN_PROGRESS
    # sitting is an open enrolment.
    exam = _practical(2026)
    _on_roster(2026)
    Sitting.objects.create(judge=judge, exam=exam, status=Status.SUBMITTED)

    assert enrol(judge, exam, official=official).status == Status.PENDING
