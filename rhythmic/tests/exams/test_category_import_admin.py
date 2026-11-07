from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from exams.awards import Category
from exams.category_import import CategoryChanges, CategoryRow, apply_categories
from exams.models import Certification, Cycle


def test_an_official_opens_the_import_page_and_sees_an_upload_form_with_cycle_chooser(
    admin_client,
):
    Cycle.objects.create(name="Cycle I", first_year=2025, last_year=2027)

    response = admin_client.get(reverse("admin:exams_certification_import"))
    assert response.status_code == 200
    assert b'name="categories"' in response.content
    assert b"Cycle I" in response.content


def test_the_import_page_rejects_a_signed_in_non_staff_user(client, django_user_model):
    user = django_user_model.objects.create_user(username="user", password="password")
    client.force_login(user)
    response = client.get(reverse("admin:exams_certification_import"))
    assert response.status_code == 302  # Redirect to login or insufficient permissions


def test_a_dry_run_writes_nothing(admin_client, judge, cycle, official):
    apply_categories(
        CategoryChanges(
            add=[CategoryRow(sagf_id=judge.sagf_id, category=Category.TWO)],
            supercedes=[],
        ),
        cycle=cycle,
        official=official,
        date=date(2026, 11, 4),
    )
    uploaded_file = SimpleUploadedFile(
        "categories.csv", b"sagf_id,category\nSAGF-0002,1\n"
    )

    response = admin_client.post(
        reverse("admin:exams_certification_import"),
        {"categories": uploaded_file, "cycle": cycle.pk},
    )

    assert response.status_code == 200
    assert list(Certification.objects.values_list("judge__sagf_id", "category")) == [
        ("SAGF-0001", 2)
    ]
    assert b"SAGF-0002" in response.content


def test_the_import_shows_the_superseded_preview(admin_client, judge, cycle, official):
    apply_categories(
        CategoryChanges(
            add=[CategoryRow(sagf_id=judge.sagf_id, category=Category.TWO)],
            supercedes=[],
        ),
        cycle=cycle,
        official=official,
        date=date(2026, 11, 4),
    )
    uploaded_file = SimpleUploadedFile(
        "categories.csv", b"sagf_id,category\nSAGF-0001,1\n"
    )

    response = admin_client.post(
        reverse("admin:exams_certification_import"),
        {"categories": uploaded_file, "cycle": cycle.pk},
    )

    assert response.status_code == 200
    assert "SAGF-0001: 2 → 1" in response.content.decode()


def test_an_error_is_shown_for_invalid_csv(admin_client, cycle):
    uploaded_file = SimpleUploadedFile(
        "categories.csv", b"sagf_id,category\nSAGF-0001,5\n"
    )

    response = admin_client.post(
        reverse("admin:exams_certification_import"),
        {"categories": uploaded_file, "cycle": cycle.pk},
    )

    assert response.status_code == 200
    assert b"Line 2: Invalid category: 5" in response.content
    assert response.context["preview"] is None
