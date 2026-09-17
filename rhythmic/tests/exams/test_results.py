from decimal import Decimal

import pytest

from exams.freeze import start_sitting
from exams.marking import record_response, submit_sitting
from exams.models import (
    ComponentPracticalItem,
    ComponentQuestion,
    ComponentResult,
    Exam,
    ExamComponent,
    ExamKind,
    GradeBandRow,
    MarkingScheme,
    MarkingTableRow,
    Sitting,
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

    questions = []
    for position in range(1, 7):
        question = Question.objects.create(
            reference=f"RG-2026-{position:03d}",
        )
        Option.objects.create(question=question, position=1, is_correct=False)
        Option.objects.create(question=question, position=2, is_correct=True)
        ComponentQuestion.objects.create(
            component=component,
            question=question,
            position=position,
        )
        questions.append(question)

    return component, questions


def _practical_component(*, exam, name, position, aspect, bands):
    comp = ExamComponent.objects.create(
        exam=exam,
        name=name,
        position=position,
        marking_scheme=MarkingScheme.NUMERIC,
        aspect=aspect,
        difference_steps=[Decimal("0.00"), Decimal("1.00")],
    )
    for band_name, minimum in bands:
        GradeBandRow.objects.create(component=comp, name=band_name, minimum=minimum)
    MarkingTableRow.objects.create(
        component=comp,
        expert_minimum=Decimal("0.00"),
        percentages=[Decimal("85.00"), Decimal("0.00")],
    )
    return comp


@pytest.mark.django_db
def test_a_component_percentage_is_the_mean_not_the_total(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    component, _ = _theory_exam_and_question(level=1)
    sitting = Sitting.objects.create(
        judge=judge,
        exam=component.exam,
    )
    start_sitting(sitting)

    items = list(sitting.items.order_by("position"))
    assert len(items) == 6

    for item in items:
        record_response(item=item, response="2")
    submit_sitting(sitting=sitting)

    result = ComponentResult.objects.get(
        sitting=sitting,
        component_name=component.name,
    )

    assert result.percentage == Decimal("100.0")


@pytest.mark.django_db
def test_the_two_band_sets_grade_the_same_percentage_differently(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)

    # 1 apparatus, 1 routine, 2 practical items (DA and AV)
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    item_da = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )
    item_av = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.AV, expert_score=Decimal("8.50")
    )

    # Component DA (Difficulty: Excellent >= 80, Very Good >= 70)
    comp_da = _practical_component(
        exam=exam,
        name="Component DA",
        position=1,
        aspect=Aspect.DA,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("50.00")),
            ("Good", Decimal("60.00")),
            ("Very Good", Decimal("70.00")),
            ("Excellent", Decimal("80.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_da, practical_item=item_da, position=1
    )

    # Component AV (Artistry/Execution: Excellent >= 90, Very Good >= 80)
    comp_av = _practical_component(
        exam=exam,
        name="Component AV",
        position=2,
        aspect=Aspect.AV,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("60.00")),
            ("Good", Decimal("70.00")),
            ("Very Good", Decimal("80.00")),
            ("Excellent", Decimal("90.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_av, practical_item=item_av, position=1
    )

    # Enrol, freeze, answer with expert score, submit
    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)

    for sitting_item in sitting.items.all():
        record_response(item=sitting_item, response="8.50")
    submit_sitting(sitting=sitting)

    da_result = ComponentResult.objects.get(
        sitting=sitting, component_name="Component DA"
    )
    av_result = ComponentResult.objects.get(
        sitting=sitting, component_name="Component AV"
    )

    assert da_result.percentage == Decimal("85.00")
    assert av_result.percentage == Decimal("85.00")
    assert da_result.grade_name == "Excellent"
    assert av_result.grade_name == "Very Good"


@pytest.mark.django_db
def test_a_practical_sitting_produces_four_component_results(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)

    # 1 apparatus, 1 routine, 4 practical items (DA, DB, AV and EX)
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    item_da = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )
    item_av = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.AV, expert_score=Decimal("8.50")
    )
    item_db = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DB, expert_score=Decimal("8.50")
    )
    item_ex = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.EX, expert_score=Decimal("8.50")
    )
    comp_da = _practical_component(
        exam=exam,
        name="Component DA",
        position=1,
        aspect=Aspect.DA,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("50.00")),
            ("Good", Decimal("60.00")),
            ("Very Good", Decimal("70.00")),
            ("Excellent", Decimal("80.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_da, practical_item=item_da, position=1
    )

    comp_db = _practical_component(
        exam=exam,
        name="Component DB",
        position=2,
        aspect=Aspect.DB,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("50.00")),
            ("Good", Decimal("60.00")),
            ("Very Good", Decimal("70.00")),
            ("Excellent", Decimal("80.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_db, practical_item=item_db, position=1
    )
    comp_av = _practical_component(
        exam=exam,
        name="Component AV",
        position=3,
        aspect=Aspect.AV,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("60.00")),
            ("Good", Decimal("70.00")),
            ("Very Good", Decimal("80.00")),
            ("Excellent", Decimal("90.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_av, practical_item=item_av, position=1
    )
    comp_ex = _practical_component(
        exam=exam,
        name="Component EX",
        position=4,
        aspect=Aspect.EX,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("60.00")),
            ("Good", Decimal("70.00")),
            ("Very Good", Decimal("80.00")),
            ("Excellent", Decimal("90.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_ex, practical_item=item_ex, position=1
    )

    # Enrol, freeze, answer with expert score, submit
    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)

    for sitting_item in sitting.items.all():
        record_response(item=sitting_item, response="8.50")
    submit_sitting(sitting=sitting)

    assert list(
        sitting.results.values_list("component_position", "component_name")
    ) == [
        (1, "Component DA"),
        (2, "Component DB"),
        (3, "Component AV"),
        (4, "Component EX"),
    ]


@pytest.mark.django_db
def test_editing_a_grade_band_does_not_regrade_a_submitted_sitting(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    item_da = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )

    comp_da = _practical_component(
        exam=exam,
        name="Component DA",
        position=1,
        aspect=Aspect.DA,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("50.00")),
            ("Good", Decimal("60.00")),
            ("Very Good", Decimal("70.00")),
            ("Excellent", Decimal("80.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_da, practical_item=item_da, position=1
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)
    for sitting_item in sitting.items.all():
        record_response(item=sitting_item, response="8.50")
    submit_sitting(sitting=sitting)
    excellent_band = comp_da.grade_bands.get(name="Excellent")
    excellent_band.minimum = Decimal("90.00")
    excellent_band.save(update_fields=["minimum"])

    assert sitting.results.get().grade_name == "Excellent"


@pytest.mark.django_db
def test_the_grade_uses_the_bands_frozen_at_start_of_sitting(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    item_da = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )

    comp_da = _practical_component(
        exam=exam,
        name="Component DA",
        position=1,
        aspect=Aspect.DA,
        bands=(
            ("Fail", Decimal("0.00")),
            ("Pass", Decimal("50.00")),
            ("Good", Decimal("60.00")),
            ("Very Good", Decimal("70.00")),
            ("Excellent", Decimal("80.00")),
        ),
    )
    ComponentPracticalItem.objects.create(
        component=comp_da, practical_item=item_da, position=1
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)
    for sitting_item in sitting.items.all():
        record_response(item=sitting_item, response="8.50")

    excellent_band = comp_da.grade_bands.get(name="Excellent")
    excellent_band.minimum = Decimal("90.00")
    excellent_band.save(update_fields=["minimum"])

    submit_sitting(sitting=sitting)
    assert sitting.results.get().grade_name == "Excellent"


@pytest.mark.django_db
def test_component_results_are_ordered_by_component_position(django_user_model):
    judge = django_user_model.objects.create_user(username="judge", password="password")
    exam = Exam.objects.create(kind=ExamKind.PRACTICAL, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)

    ComponentResult.objects.create(
        sitting=sitting,
        component_name="Component EX",
        component_position=3,
        percentage=Decimal("85.00"),
        grade_name="Very Good",
    )
    ComponentResult.objects.create(
        sitting=sitting,
        component_name="Component DA",
        component_position=1,
        percentage=Decimal("85.00"),
        grade_name="Very Good",
    )

    ComponentResult.objects.create(
        sitting=sitting,
        component_name="Component DB",
        component_position=2,
        percentage=Decimal("85.00"),
        grade_name="Very Good",
    )

    assert list(
        sitting.results.values_list("component_position", "component_name")
    ) == [
        (1, "Component DA"),
        (2, "Component DB"),
        (3, "Component EX"),
    ]
