from decimal import Decimal

import pytest
from django.urls import reverse

from questions.models import Apparatus, Aspect, PracticalItem, Question, Routine


@pytest.mark.django_db
def test_question_changelist_renders(client, admin_user):
    q = Question.objects.create(reference="Check this returns")
    client.force_login(admin_user)
    url = reverse("admin:questions_question_changelist")

    response = client.get(url)
    assert q.reference in response.content.decode("utf-8")


@pytest.mark.django_db
def test_practicalitem_changelist_renders(client, admin_user):

    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        label="Routine 1",
        apparatus=apparatus,
        video="routines/routine1.mp4",
    )
    PracticalItem.objects.create(
        routine=routine, aspect="DB", expert_score=Decimal("5.00")
    )

    client.force_login(admin_user)
    url = reverse("admin:questions_practicalitem_changelist")

    response = client.get(url)
    assert str(routine) in response.content.decode("utf-8")


@pytest.mark.django_db
def test_practicalitem_changelist_offers_an_aspect_filter(client, admin_user):
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        label="Routine 1",
        apparatus=apparatus,
        video="routines/routine1.mp4",
    )
    PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("5.00")
    )

    client.force_login(admin_user)
    url = reverse("admin:questions_practicalitem_changelist")

    response = client.get(url)
    # the full query param, not a bare "DA": that appears in the row regardless
    assert "?aspect__exact=DA" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_practicalitem_changelist_uses_select_related(
    admin_client, django_assert_num_queries
):
    apparatuses = [
        Apparatus.objects.create(name=f"Apparatus {position}", position=position)
        for position in range(1, 6)
    ]
    for apparatus in apparatuses:
        routine = Routine.objects.create(
            apparatus=apparatus,
            label=f"Routine {apparatus.position}",
            video=f"routines/routine{apparatus.position}.mp4",
        )
        for aspect in Aspect:
            PracticalItem.objects.create(
                routine=routine, aspect=aspect, expert_score=Decimal("5.00")
            )

    url = reverse("admin:questions_practicalitem_changelist")

    with django_assert_num_queries(5):
        response = admin_client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_practicalitem_admin_history_shows_old_and_new_values(admin_client):
    apparatus = Apparatus.objects.create(name="Rope", position=1)
    routine = Routine.objects.create(
        apparatus=apparatus,
        label="Routine 1",
        video="routines/routine1.mp4",
    )
    practical_item = PracticalItem.objects.create(
        routine=routine, aspect=Aspect.DA, expert_score=Decimal("4.20")
    )

    practical_item.expert_score = Decimal("4.50")
    practical_item.save()

    url = reverse("admin:questions_practicalitem_history", args=[practical_item.pk])
    response = admin_client.get(url)
    body = response.content.decode("utf-8")

    # The current value also appears in PracticalItem.__str__ page chrome.
    assert "4.50" in body
    assert "4.20" in body


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:questions_question_changelist",
        "admin:questions_apparatus_changelist",
        "admin:questions_routine_changelist",
        "admin:questions_option_changelist",
        "admin:questions_practicalitem_changelist",
    ],
)
def test_admin_pages_require_login(client, url_name):
    url = reverse(url_name)
    response = client.get(url)
    assert response.status_code == 302
    assert "/admin/login/" in response.url


@pytest.mark.django_db
def test_a_question_with_one_correct_option_saves_successfully(client, admin_user):
    question = Question.objects.create(reference="Test Question")
    client.force_login(admin_user)
    url = reverse("admin:questions_question_change", args=[question.id])

    data = {
        "reference": "Test Question",
        "blocks-TOTAL_FORMS": "0",
        "blocks-INITIAL_FORMS": "0",
        "blocks-MIN_NUM_FORMS": "0",
        "blocks-MAX_NUM_FORMS": "1000",
        "options-TOTAL_FORMS": "1",
        "options-INITIAL_FORMS": "0",
        "options-MIN_NUM_FORMS": "0",
        "options-MAX_NUM_FORMS": "1000",
        "options-0-position": "1",
        "options-0-is_correct": "on",
        "_save": "Save",
    }

    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse("admin:questions_question_changelist")
    # Pylance may report `Question` has no attribute `options`, but this reverse
    # accessor is created dynamically by Django from Option.related_name.
    assert question.options.filter(is_correct=True).count() == 1  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_a_question_with_no_correct_option_raises_validation_error(client, admin_user):
    question = Question.objects.create(reference="Test Question")
    client.force_login(admin_user)
    url = reverse("admin:questions_question_change", args=[question.id])

    data = {
        "reference": "Test Question",
        "blocks-TOTAL_FORMS": "0",
        "blocks-INITIAL_FORMS": "0",
        "blocks-MIN_NUM_FORMS": "0",
        "blocks-MAX_NUM_FORMS": "1000",
        "options-TOTAL_FORMS": "1",
        "options-INITIAL_FORMS": "0",
        "options-MIN_NUM_FORMS": "0",
        "options-MAX_NUM_FORMS": "1000",
        "options-0-position": "1",
        "_save": "Save",
    }

    response = client.post(url, data)
    assert response.status_code == 200
    assert "There must be exactly one correct option." in response.content.decode(
        "utf-8"
    )
    # Pylance may report `Question` has no attribute `options`, but this reverse
    # accessor is created dynamically by Django from Option.related_name.
    assert question.options.count() == 0  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_a_question_with_multiple_correct_options_raises_validation_error(
    client, admin_user
):
    question = Question.objects.create(reference="Test Question")
    client.force_login(admin_user)
    url = reverse("admin:questions_question_change", args=[question.id])

    data = {
        "reference": "Test Question",
        "blocks-TOTAL_FORMS": "0",
        "blocks-INITIAL_FORMS": "0",
        "blocks-MIN_NUM_FORMS": "0",
        "blocks-MAX_NUM_FORMS": "1000",
        "options-TOTAL_FORMS": "2",
        "options-INITIAL_FORMS": "0",
        "options-MIN_NUM_FORMS": "0",
        "options-MAX_NUM_FORMS": "1000",
        "options-0-position": "1",
        "options-0-is_correct": "on",
        "options-1-position": "2",
        "options-1-is_correct": "on",
        "_save": "Save",
    }

    response = client.post(url, data)
    assert response.status_code == 200
    assert "There must be exactly one correct option." in response.content.decode(
        "utf-8"
    )
    # Pylance may report `Question` has no attribute `options`, but this reverse
    # accessor is created dynamically by Django from Option.related_name.
    assert question.options.count() == 0  # type: ignore[attr-defined]
