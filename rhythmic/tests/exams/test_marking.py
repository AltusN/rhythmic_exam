from decimal import Decimal

import pytest

from exams.freeze import start_sitting
from exams.marking import SittingNotInProgress, record_response, submit_sitting
from exams.models import (
    ComponentPracticalItem,
    ComponentQuestion,
    Exam,
    ExamComponent,
    ExamKind,
    GradeBandRow,
    MarkingScheme,
    MarkingTableRow,
    Sitting,
    SittingItem,
)
from questions.models import Apparatus, Aspect, Option, PracticalItem, Question, Routine


def _theory_exam_and_component(*, level: int) -> ExamComponent:
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=level, year=2026)
    component = ExamComponent.objects.create(
        exam=exam,
        name="Theory Component",
        position=1,
        marking_scheme=MarkingScheme.CHOICE,
        aspect="",
        difference_steps=[],
    )
    for name, minimum in (
        ("Fail", Decimal("0.00")),
        ("Pass", Decimal("50.00")),
        ("Good", Decimal("65.00")),
        ("Excellent", Decimal("80.00")),
    ):
        GradeBandRow.objects.create(component=component, name=name, minimum=minimum)
    return component


def _theory_exam_and_question(*, level: int = 1):
    component = _theory_exam_and_component(level=level)

    question = Question.objects.create(reference="RG-2026-001")

    Option.objects.create(
        question=question,
        position=1,
        is_correct=False,
    )
    Option.objects.create(
        question=question,
        position=2,
        is_correct=True,
    )
    ComponentQuestion.objects.create(
        component=component,
        question=question,
        position=1,
    )

    return component, question


@pytest.mark.django_db
def test_a_correct_response_scores_full_marks(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    component, _ = _theory_exam_and_question(level=1)
    sitting = Sitting.objects.create(
        judge=judge,
        exam=component.exam,
    )

    start_sitting(sitting)
    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="2")

    submit_sitting(sitting)

    fresh = SittingItem.objects.get(pk=item.pk)
    assert fresh.percentage == Decimal("100")


@pytest.mark.django_db
def test_an_unanswered_item_scores_zero_but_is_not_absent(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    component, _ = _theory_exam_and_question(level=1)
    sitting = Sitting.objects.create(
        judge=judge,
        exam=component.exam,
    )

    start_sitting(sitting)
    item = SittingItem.objects.get(sitting=sitting)

    # Do not record any response for the item

    submit_sitting(sitting)

    fresh = SittingItem.objects.get(pk=item.pk)
    assert fresh.percentage == Decimal("0")


@pytest.mark.django_db
def test_a_numeric_response_is_marked_through_the_marking_table(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)

    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    practical_item = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )

    component = ExamComponent.objects.create(
        exam=exam,
        name="Component DA",
        position=1,
        marking_scheme=MarkingScheme.NUMERIC,
        aspect=Aspect.DA,
        difference_steps=[
            Decimal("0.10"),
            Decimal("0.20"),
            Decimal("0.50"),
            Decimal("1.00"),
        ],
    )
    for name, minimum in (
        ("Fail", Decimal("0.00")),
        ("Pass", Decimal("50.00")),
        ("Good", Decimal("65.00")),
        ("Excellent", Decimal("80.00")),
    ):
        GradeBandRow.objects.create(component=component, name=name, minimum=minimum)
    MarkingTableRow.objects.create(
        component=component,
        expert_minimum=Decimal("0.00"),
        percentages=[
            Decimal("100"),
            Decimal("90"),
            Decimal("50"),
            Decimal("0"),
        ],
    )
    MarkingTableRow.objects.create(
        component=component,
        expert_minimum=Decimal("5.00"),
        percentages=[
            Decimal("100"),
            Decimal("80"),
            Decimal("40"),
            Decimal("0"),
        ],
    )
    ComponentPracticalItem.objects.create(
        component=component,
        practical_item=practical_item,
        position=1,
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="8.20")
    submit_sitting(sitting)

    fresh = SittingItem.objects.get(pk=item.pk)
    # row 1 (expert 8.50 >= 5.00), column 1 (difference 0.30 in [0.20, 0.50))
    assert fresh.percentage == Decimal("80")


def _practical_sitting(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)

    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    practical_item = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )

    component = ExamComponent.objects.create(
        exam=exam,
        name="Component DA",
        position=1,
        marking_scheme=MarkingScheme.NUMERIC,
        aspect=Aspect.DA,
        difference_steps=[
            Decimal("0.10"),
            Decimal("0.20"),
            Decimal("0.50"),
            Decimal("1.00"),
        ],
    )
    for name, minimum in (
        ("Fail", Decimal("0.00")),
        ("Pass", Decimal("50.00")),
        ("Good", Decimal("65.00")),
        ("Excellent", Decimal("80.00")),
    ):
        GradeBandRow.objects.create(component=component, name=name, minimum=minimum)
    MarkingTableRow.objects.create(
        component=component,
        expert_minimum=Decimal("0.00"),
        percentages=[
            Decimal("100"),
            Decimal("90"),
            Decimal("50"),
            Decimal("0"),
        ],
    )
    MarkingTableRow.objects.create(
        component=component,
        expert_minimum=Decimal("5.00"),
        percentages=[
            Decimal("100"),
            Decimal("80"),
            Decimal("40"),
            Decimal("0"),
        ],
    )
    ComponentPracticalItem.objects.create(
        component=component,
        practical_item=practical_item,
        position=1,
    )

    return Sitting.objects.create(judge=judge, exam=exam)


@pytest.mark.django_db
def test_an_unreadable_numeric_response_scores_zero(django_user_model):
    sitting = _practical_sitting(django_user_model)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="not a number")
    submit_sitting(sitting)

    fresh = SittingItem.objects.get(pk=item.pk)
    assert fresh.percentage == Decimal("0")


@pytest.mark.django_db
def test_a_submitted_sitting_refuses_further_responses(django_user_model):
    sitting = _practical_sitting(django_user_model)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="8.20")
    submit_sitting(sitting)

    with pytest.raises(SittingNotInProgress):
        record_response(item=item, response="9.00")


@pytest.mark.django_db
def test_marks_are_not_recomputed_after_submission(django_user_model):
    sitting = _practical_sitting(django_user_model)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="8.20")
    submit_sitting(sitting)

    MarkingTableRow.objects.filter(expert_minimum=Decimal("5.00")).update(
        percentages=[Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
    )
    PracticalItem.objects.update(expert_score=Decimal("1.00"))

    assert MarkingTableRow.objects.get(expert_minimum=Decimal("5.00")).percentages == [
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
        Decimal("40"),
    ]
    assert PracticalItem.objects.get().expert_score == Decimal("1.00")

    assert SittingItem.objects.get(pk=item.pk).percentage == Decimal("80")


@pytest.mark.django_db
def test_the_mark_uses_the_table_frozen_at_start_of_sitting(django_user_model):
    sitting = _practical_sitting(django_user_model)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="8.20")

    MarkingTableRow.objects.filter(expert_minimum=Decimal("5.00")).update(
        percentages=[Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
    )
    PracticalItem.objects.update(expert_score=Decimal("1.00"))

    submit_sitting(sitting)

    fresh = SittingItem.objects.get(pk=item.pk)
    assert fresh.percentage == Decimal("80")

    assert MarkingTableRow.objects.get(expert_minimum=Decimal("5.00")).percentages == [
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
        Decimal("40"),
    ]
    assert PracticalItem.objects.get().expert_score == Decimal("1.00")


@pytest.mark.django_db
def test_submitting_twice_raises_an_exception(django_user_model):
    sitting = _practical_sitting(django_user_model)
    start_sitting(sitting)

    item = SittingItem.objects.get(sitting=sitting)

    record_response(item=item, response="8.20")
    submit_sitting(sitting)

    with pytest.raises(SittingNotInProgress):
        submit_sitting(sitting)
