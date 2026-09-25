from decimal import Decimal

import pytest
from django.urls import reverse

from exams.freeze import start_sitting
from exams.marking import submit_sitting
from exams.models import (
    ComponentQuestion,
    Exam,
    ExamComponent,
    ExamKind,
    GradeBandRow,
    MarkingScheme,
    Sitting,
    SittingItem,
    Status,
)
from exams.models.sitting import ComponentResult
from questions.models import Apparatus, Aspect, Option, PracticalItem, Question, Routine


@pytest.mark.django_db
def test_the_exam_changelist_renders_an_exam(admin_client):
    url = reverse("admin:exams_exam_changelist")
    response = admin_client.get(url)

    assert "2029" not in response.content.decode()

    Exam.objects.create(level=7, year=2029, kind=ExamKind.THEORY)

    response = admin_client.get(url)
    assert "2029 - Level 7 - THEORY" in response.content.decode()


@pytest.mark.django_db
def test_the_exam_change_page_has_a_component_inline(admin_client):
    exam = Exam.objects.create(level=1, year=2026, kind=ExamKind.THEORY)

    url = reverse("admin:exams_exam_change", args=[exam.pk])
    response = admin_client.get(url)

    # the management form's hidden input, keyed by ExamComponent.exam's related_name
    assert 'name="components-TOTAL_FORMS"' in response.content.decode()


@pytest.mark.django_db
def test_a_practical_component_takes_members_through_the_admin(admin_client):
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus, label="R1", video="blocks/rope.mp4"
    )
    practical_item = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("8.50")
    )
    exam = Exam.objects.create(level=1, year=2026, kind=ExamKind.PRACTICAL)
    component = ExamComponent.objects.create(
        exam=exam,
        name="Compnent DA",
        position=1,
        marking_scheme=MarkingScheme.NUMERIC,
        aspect=Aspect.DA,
        difference_steps=[Decimal("0.10"), Decimal("1.00")],
    )
    url = reverse("admin:exams_examcomponent_change", args=[component.pk])

    data = {
        # the components own form
        "exam": exam.pk,
        "name": "Compnent DA",
        "position": 1,
        "marking_scheme": MarkingScheme.NUMERIC,
        "aspect": Aspect.DA,
        "difference_steps": "0.10, 1.00",
        "question_members-TOTAL_FORMS": "0",
        "question_members-INITIAL_FORMS": "0",
        "question_members-MIN_NUM_FORMS": "0",
        "question_members-MAX_NUM_FORMS": "1000",
        # the inline under test
        "practical_item_members-TOTAL_FORMS": "1",
        "practical_item_members-INITIAL_FORMS": "0",
        "practical_item_members-MIN_NUM_FORMS": "0",
        "practical_item_members-MAX_NUM_FORMS": "1000",
        "practical_item_members-0-practical_item": practical_item.pk,
        "practical_item_members-0-position": "1",
        # the other three inlines, present but empty
        "marking_rows-TOTAL_FORMS": "0",
        "marking_rows-INITIAL_FORMS": "0",
        "marking_rows-MIN_NUM_FORMS": "0",
        "marking_rows-MAX_NUM_FORMS": "1000",
        "grade_bands-TOTAL_FORMS": "0",
        "grade_bands-INITIAL_FORMS": "0",
        "grade_bands-MIN_NUM_FORMS": "0",
        "grade_bands-MAX_NUM_FORMS": "1000",
        "_save": "Save",
    }

    response = admin_client.post(url, data)
    assert response.status_code == 302
    assert (
        component.practical_item_members.filter(practical_item=practical_item).count()
        == 1
    )


def test_a_sitting_item_cannot_be_changed_through_the_admin(
    admin_client, django_user_model
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)
    item = SittingItem.objects.create(
        sitting=sitting,
        component_name="Component A",
        component_position=1,
        marking_scheme=MarkingScheme.CHOICE,
        grade_bands=[{"minimum": 0, "name": "Pass"}],
        position=1,
        question_snapshot={"reference": "original"},
        marking_key={"correct_option": "1"},
    )

    url = reverse("admin:exams_sittingitem_change", args=[item.pk])
    # every field non-empty: Django treats {} and [] as "required" failures,
    # so an empty payload would pass even without the read-only guard
    admin_client.post(
        url,
        {
            "sitting": sitting.pk,
            "component_name": "Tampered",
            "component_position": 1,
            "marking_scheme": MarkingScheme.CHOICE,
            "position": 1,
            "question_snapshot": '{"reference": "tampered"}',
            "marking_key": '{"correct_option": "2"}',
            "grade_bands": '[{"minimum": 0, "name": "Pass"}]',
            "response": '{"answer": "1"}',
            "percentage": "50.00",
            "_save": "Save",
        },
    )

    fresh = SittingItem.objects.get(pk=item.pk)
    assert fresh.component_name == "Component A"
    assert fresh.question_snapshot == {"reference": "original"}


def test_a_sitting_item_cannot_be_deleted_through_the_admin(
    admin_client, django_user_model
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)
    item = SittingItem.objects.create(
        sitting=sitting,
        component_name="Component A",
        component_position=1,
        marking_scheme=MarkingScheme.CHOICE,
        grade_bands=[{"minimum": 0, "name": "Pass"}],
        position=1,
        question_snapshot={"reference": "original"},
        marking_key={"correct_option": "1"},
    )

    url = reverse("admin:exams_sittingitem_delete", args=[item.pk])
    admin_client.post(url, {"post": "yes"})

    assert SittingItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_the_sitting_history_page_shows_the_previous_status(
    admin_client, django_user_model
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)

    sitting.status = Status.IN_PROGRESS
    sitting.save()

    url = reverse("admin:exams_sitting_history", args=[sitting.pk])
    response = admin_client.get(url)

    assert "PENDING" in response.content.decode()


@pytest.mark.django_db
def test_a_component_result_cannot_be_changed_through_the_admin(
    admin_client, django_user_model
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)
    result = ComponentResult.objects.create(
        sitting=sitting,
        component_name="Component A",
        component_position=1,
        percentage=Decimal("80.00"),
        grade_name="Excellent",
    )

    url = reverse("admin:exams_componentresult_change", args=[result.pk])
    admin_client.post(
        url,
        {
            "sitting": sitting.pk,
            "component_name": "Tampered",
            "component_position": 1,
            "percentage": "0.00",
            "grade_name": "Fail",
            "_save": "Save",
        },
    )

    fresh = ComponentResult.objects.get(pk=result.pk)
    assert fresh.component_name == "Component A"
    assert fresh.percentage == Decimal("80.00")


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:exams_exam_changelist",
        "admin:exams_examcomponent_changelist",
        "admin:exams_sittingitem_changelist",
        "admin:exams_sitting_changelist",
        "admin:exams_componentresult_changelist",
    ],
)
def test_admin_pages_require_login(client, url_name):
    url = reverse(url_name)
    response = client.get(url)
    assert response.status_code == 302
    assert "/admin/login/" in response.url


@pytest.mark.django_db
def test_a_sitting_cannot_be_changed_through_the_admin(admin_client, django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
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
    ):
        GradeBandRow.objects.create(component=component, name=name, minimum=minimum)
    question = Question.objects.create(reference="RG-2026-001")
    Option.objects.create(question=question, position=1, is_correct=False)
    Option.objects.create(question=question, position=2, is_correct=True)
    ComponentQuestion.objects.create(component=component, question=question, position=1)

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)
    submit_sitting(sitting)

    url = reverse("admin:exams_sitting_change", args=[sitting.pk])
    # DateTimeField renders as a split widget: one key for the date, one for the time
    # A 403 is the one response only the lock produces: a form that fails validation
    # re-renders with 200 and ALSO leaves the row unchanged, so the data assertion
    # below cannot tell the two apart on its own. That happened on 2026-09-25, when
    # Sitting gained a required candidate_number this payload lacked and the test went
    # green against an editable admin.
    response = admin_client.post(
        url,
        {
            "judge": sitting.judge.pk,
            "exam": sitting.exam.pk,
            "status": Status.IN_PROGRESS,
            "outcome": "",
            "certified_by": "",
            "started_at_0": "",
            "started_at_1": "",
            "submitted_at_0": "",
            "submitted_at_1": "",
            "certified_at_0": "",
            "certified_at_1": "",
            "candidate_number": sitting.candidate_number,
            "override_by": "",
            "override_reason": "",
            "_save": "Save",
        },
    )
    assert response.status_code == 403

    sitting.refresh_from_db()
    assert sitting.status == Status.SUBMITTED


@pytest.mark.django_db
def test_a_component_result_cannot_be_deleted_through_the_admin(
    admin_client, django_user_model
):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
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
    ):
        GradeBandRow.objects.create(component=component, name=name, minimum=minimum)
    question = Question.objects.create(reference="RG-2026-001")
    Option.objects.create(question=question, position=1, is_correct=False)
    Option.objects.create(question=question, position=2, is_correct=True)
    ComponentQuestion.objects.create(component=component, question=question, position=1)

    sitting = Sitting.objects.create(judge=judge, exam=exam)
    start_sitting(sitting)
    submit_sitting(sitting)
    # get() raises if submit_sitting produced no result, so the setup checks itself
    result = sitting.results.get()

    url = reverse("admin:exams_componentresult_delete", args=[result.pk])
    admin_client.post(url, {"post": "yes"})

    assert ComponentResult.objects.filter(pk=result.pk).exists()


@pytest.mark.django_db
def test_a_sitting_cannot_be_deleted_through_the_admin(admin_client, django_user_model):
    judge = django_user_model.objects.create_user(username="Judge Judy", password="x")
    exam = Exam.objects.create(kind=ExamKind.THEORY, level=1, year=2026)
    sitting = Sitting.objects.create(judge=judge, exam=exam)

    url = reverse("admin:exams_sitting_delete", args=[sitting.pk])
    admin_client.post(url, {"post": "yes"})

    assert Sitting.objects.filter(pk=sitting.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    [
        "admin:exams_sittingitem_add",
        "admin:exams_componentresult_add",
        "admin:exams_sitting_add",
    ],
)
def test_sitting_records_cannot_be_added_through_the_admin(admin_client, url_name):
    url = reverse(url_name)
    response = admin_client.get(url)

    assert response.status_code == 403
