from decimal import Decimal

import pytest

from exams.freeze import QuestionHasNoAnswer, SittingAlreadyStarted, start_sitting
from exams.models import (
    ComponentPracticalItem,
    ComponentQuestion,
    Exam,
    ExamComponent,
    ExamKind,
    MarkingScheme,
    MarkingTableRow,
    Sitting,
    SittingItem,
)
from questions.models import (
    Apparatus,
    Aspect,
    Kind,
    Option,
    PracticalItem,
    Question,
    QuestionBlock,
    Routine,
)


def _theory_exam_and_component(*, level: int) -> ExamComponent:
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=level, year=2026)
    return ExamComponent.objects.create(
        exam=exam,
        name="Theory Component",
        position=1,
        marking_scheme=MarkingScheme.CHOICE,
        aspect="",
        difference_steps=[],
    )


@pytest.mark.django_db
def test_the_snapshot_survives_editing_the_question(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    component = _theory_exam_and_component(level=1)
    exam = component.exam
    text = "the original wording"

    question = Question.objects.create(reference="RG-2026-014")
    question_block = QuestionBlock.objects.create(
        question=question, position=1, kind=Kind.TEXT, text=text
    )
    option_1 = Option.objects.create(question=question, position=1, is_correct=False)
    option_2 = Option.objects.create(question=question, position=2, is_correct=True)
    ComponentQuestion.objects.create(
        component=component,
        question=question,
        position=1,
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)

    start_sitting(sitting)
    item = sitting.items.get()

    question.blocks.update(text="rewritten text")
    option_2.is_correct = False
    option_2.save()
    option_1.is_correct = True
    option_1.save()

    assert QuestionBlock.objects.get(pk=question_block.pk).text == "rewritten text"
    assert Option.objects.get(pk=option_1.pk).is_correct is True

    fresh = SittingItem.objects.get(pk=item.pk)

    assert fresh.question_snapshot["blocks"][0]["text"] == text
    assert fresh.marking_key["correct_option"] == "2"


@pytest.mark.django_db
def test_starting_an_already_started_sitting_raises(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    component = _theory_exam_and_component(level=1)
    exam = component.exam

    question = Question.objects.create(reference="RG-2026-099")
    Option.objects.create(question=question, position=1, is_correct=True)
    ComponentQuestion.objects.create(
        component=component,
        question=question,
        position=1,
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)
    # deliberately not refreshed — this object still says PENDING
    with pytest.raises(SittingAlreadyStarted):
        start_sitting(sitting)


def _question_with_correct_option(reference: str) -> Question:
    question = Question.objects.create(reference=reference)
    Option.objects.create(question=question, position=1, is_correct=True)
    return question


@pytest.mark.django_db
def test_starting_a_sitting_creates_one_item_per_member(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)

    # two components, with a different number of members each, so per-component
    # or per-sitting counts can't be confused with per-member. Distinct aspects
    # only to satisfy uq_one_component_per_aspect_per_exam; marking scheme stays
    # CHOICE so both use the same freeze path as theory.
    component_a = ExamComponent.objects.create(
        exam=exam,
        name="Component A",
        position=1,
        marking_scheme=MarkingScheme.CHOICE,
        aspect=Aspect.DA,
        difference_steps=[],
    )
    component_b = ExamComponent.objects.create(
        exam=exam,
        name="Component B",
        position=2,
        marking_scheme=MarkingScheme.CHOICE,
        aspect=Aspect.DB,
        difference_steps=[],
    )

    references_by_component = {
        component_a: ["RG-2026-100", "RG-2026-101"],
        component_b: ["RG-2026-200", "RG-2026-201", "RG-2026-202"],
    }
    for component, references in references_by_component.items():
        for position, reference in enumerate(references, start=1):
            ComponentQuestion.objects.create(
                component=component,
                question=_question_with_correct_option(reference),
                position=position,
            )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)

    total_members = sum(len(refs) for refs in references_by_component.values())
    items = list(sitting.items.order_by("position"))

    assert len(items) == total_members
    assert [item.position for item in items] == list(range(1, total_members + 1))
    assert [item.question_snapshot["reference"] for item in items] == [
        reference
        for references in references_by_component.values()
        for reference in references
    ]


@pytest.mark.django_db
def test_a_frozen_response_starts_null_not_empty(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)

    component = ExamComponent.objects.create(
        exam=exam,
        name="Component A",
        position=1,
        marking_scheme=MarkingScheme.CHOICE,
        aspect=Aspect.DA,
        difference_steps=[],
    )

    question = _question_with_correct_option("RG-2026-300")
    ComponentQuestion.objects.create(
        component=component,
        question=question,
        position=1,
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)

    item = sitting.items.first()
    assert item.response is None


@pytest.mark.django_db
def test_items_come_back_in_position_order(django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)

    # inserted out of position order — a bare queryset must still come back sorted
    for position in (3, 1, 2):
        SittingItem.objects.create(
            sitting=sitting,
            component_name="Component A",
            component_position=1,
            marking_scheme=MarkingScheme.CHOICE,
            position=position,
            question_snapshot={},
            marking_key={},
        )

    assert [item.position for item in sitting.items.all()] == [1, 2, 3]


@pytest.mark.django_db
def test_the_marking_key_holds_the_expert_score_as_a_string(django_user_model):
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
        ],
    )
    MarkingTableRow.objects.create(
        component=component,
        expert_minimum=Decimal("8.50"),
        percentages=[
            Decimal("100.00"),
            Decimal("50.00"),
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

    assert isinstance(item.marking_key["expert_score"], str)
    # kills str(float(x)) — float(Decimal("8.50")) loses the trailing zero
    assert item.marking_key["expert_score"] == "8.50"


@pytest.mark.django_db
def test_starting_a_sitting_does_not_issue_a_query_per_member(
    django_user_model, django_assert_num_queries
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    component = _theory_exam_and_component(level=1)
    exam = component.exam

    for position in range(1, 76):
        ComponentQuestion.objects.create(
            component=component,
            question=_question_with_correct_option(f"RG-2026-{position:03d}"),
            position=position,
        )

    sitting = Sitting.objects.create(judge=judge, exam=exam)

    # deliberately low — pins the query count so an N+1 regression fails loudly
    with django_assert_num_queries(13):
        start_sitting(sitting)


@pytest.mark.django_db
def test_starting_a_sitting_raises_on_a_question_with_no_correct_option(
    django_user_model,
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    component = _theory_exam_and_component(level=1)
    exam = component.exam

    question = Question.objects.create(reference="RG-2026-400")
    Option.objects.create(question=question, position=1, is_correct=False)
    ComponentQuestion.objects.create(
        component=component,
        question=question,
        position=1,
    )

    sitting = Sitting.objects.create(judge=judge, exam=exam)

    with pytest.raises(QuestionHasNoAnswer):
        start_sitting(sitting)
