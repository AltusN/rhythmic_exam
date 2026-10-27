import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import RosterEntry
from accounts.roster import RosterChanges, RosterRow


def test_the_import_page_shows_the_upload_form(admin_client):
    response = admin_client.get(reverse("admin:accounts_rosterentry_import"))
    assert response.status_code == 200
    assert b'name="roster"' in response.content


@pytest.mark.django_db
def test_the_import_page_rejects_a_signed_in_non_staff_user(client, django_user_model):
    user = django_user_model.objects.create_user(username="user", password="password")
    client.force_login(user)
    response = client.get(reverse("admin:accounts_rosterentry_import"))
    assert response.status_code == 302


def test_a_dry_run_writes_nothing(admin_client):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="a@example.com",
        year=2027,
        levels=(1,),
    )

    file = SimpleUploadedFile(
        "roster.csv", b"sagf_id,email,levels\nSAGF-0002,b@example.com,1\n"
    )
    response = admin_client.post(
        reverse("admin:accounts_rosterentry_import"), {"roster": file, "year": 2027}
    )
    assert list(RosterEntry.objects.values_list("sagf_id", flat=True)) == ["SAGF-0001"]
    assert b"SAGF-0002" in response.content
    assert response.status_code == 200


def test_a_fresh_page_shows_no_earlier_preview(admin_client):
    file = SimpleUploadedFile(
        "roster.csv", b"sagf_id,email,levels\nSAGF-0002,b@example.com,1\n"
    )
    url = reverse("admin:accounts_rosterentry_import")
    posted = admin_client.post(url, {"roster": file, "year": 2027})
    assert b"SAGF-0002" in posted.content

    response = admin_client.get(url)
    assert response.status_code == 200
    assert b"SAGF-0002" not in response.content


def test_the_preview_lists_adds_changes_and_removes(admin_client):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="a@example.com",
        year=2027,
        levels=(1,),
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0003",
        email="c@example.com",
        year=2027,
        levels=(1,),
    )

    upload = SimpleUploadedFile(
        "roster.csv",
        b"sagf_id,email,levels\n"
        b"SAGF-0002,b@example.com,1\n"
        b"SAGF-0003,c@example.com,1;2\n",
    )
    response = admin_client.post(
        reverse("admin:accounts_rosterentry_import"),
        {"roster": upload, "year": 2027},
    )

    assert response.status_code == 200
    assert response.context["preview"] == RosterChanges(
        add=[RosterRow("SAGF-0002", "b@example.com", (1,))],
        change=[
            (
                RosterRow("SAGF-0003", "c@example.com", (1,)),
                RosterRow("SAGF-0003", "c@example.com", (1, 2)),
            )
        ],
        remove=[RosterRow("SAGF-0001", "a@example.com", (1,))],
    )
    for sagf_id in (b"SAGF-0001", b"SAGF-0002", b"SAGF-0003"):
        assert sagf_id in response.content


def test_a_file_with_errors_shows_them_and_no_preview(admin_client):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="a@example.com",
        year=2027,
        levels=(1,),
    )
    url = reverse("admin:accounts_rosterentry_import")

    # Positive control: the error text isn't already present on a clean page.
    page = admin_client.get(url)
    assert b"is not a whole number" not in page.content
    assert b"Line 3" not in page.content

    upload = SimpleUploadedFile(
        "roster.csv",
        b"sagf_id,email,levels\n"
        b"SAGF-0003,c@example.com,1\n"
        b"SAGF-0002,b@example.com,two\n",
    )
    response = admin_client.post(url, {"roster": upload, "year": 2027})

    assert response.status_code == 200
    assert response.context["preview"] is None
    assert b"is not a whole number" in response.content
    assert b"Line 3" in response.content


def test_confirming_applies_the_import_as_the_official(admin_client, admin_user):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="a@example.com",
        year=2027,
        levels=(1,),
    )
    url = reverse("admin:accounts_rosterentry_import")

    upload = SimpleUploadedFile(
        "roster.csv",
        b"sagf_id,email,levels\n"
        b"SAGF-0001,b@example.com,1;2\n"
        b"SAGF-0002,b@example.com,1\n",
    )
    confirm_url = reverse("admin:accounts_rosterentry_confirm")
    response = admin_client.post(url, {"roster": upload, "year": 2027})
    assert response.status_code == 200
    assert confirm_url.encode() in response.content

    response = admin_client.post(confirm_url)

    # Query the database to check the current state of the roster entries for the year 2027
    roster_entries = list(
        RosterEntry.objects.filter(year=2027)
        .order_by("sagf_id")
        .values_list("sagf_id", "email", "levels")
    )

    assert roster_entries == [
        ("SAGF-0001", "b@example.com", [1, 2]),
        ("SAGF-0002", "b@example.com", [1]),
    ]
    assert (
        RosterEntry.history.filter(sagf_id="SAGF-0002").get().history_user == admin_user
    )


def test_confirming_a_stale_preview_changes_nothing(admin_client):
    RosterEntry.objects.create(
        sagf_id="SAGF-0001",
        email="a@example.com",
        year=2027,
        levels=(1,),
    )
    url = reverse("admin:accounts_rosterentry_import")

    upload = SimpleUploadedFile(
        "roster.csv",
        b"sagf_id,email,levels\nSAGF-0001,b@example.com,1\n",
    )
    confirm_url = reverse("admin:accounts_rosterentry_confirm")
    response = admin_client.post(url, {"roster": upload, "year": 2027})
    assert response.status_code == 200

    # update the email
    RosterEntry.objects.filter(sagf_id="SAGF-0001", year=2027).update(
        email="c@example.com"
    )

    response = admin_client.post(confirm_url, follow=True)
    assert b"changed since the preview" in response.content

    # The roster entry should remain unchanged
    entry = RosterEntry.objects.get(sagf_id="SAGF-0001", year=2027)
    assert entry.email == "c@example.com"
    assert entry.levels == [1]


def test_the_confirm_url_refuses_a_get(admin_client):
    upload = SimpleUploadedFile(
        "roster.csv",
        b"sagf_id,email,levels\nSAGF-0001,b@example.com,1\n",
    )
    url = reverse("admin:accounts_rosterentry_import")
    response = admin_client.post(url, {"roster": upload, "year": 2027})
    confirm_url = reverse("admin:accounts_rosterentry_confirm")
    response = admin_client.get(confirm_url)
    assert list(RosterEntry.objects.values_list("sagf_id", flat=True)) == []
    assert response.status_code == 405  # Method Not Allowed


def test_confirming_with_nothing_waiting_says_so(admin_client):
    confirm_url = reverse("admin:accounts_rosterentry_confirm")
    response = admin_client.post(confirm_url, follow=True)
    assert b"No roster import to confirm." in response.content


def test_an_excel_csv_with_a_byte_order_mark_previews(admin_client):
    upload = SimpleUploadedFile(
        "roster.csv",
        b"\xef\xbb\xbf"  # Byte Order Mark
        b"sagf_id,email,levels\n"
        b"SAGF-0001,b@example.com,1\n",
    )
    url = reverse("admin:accounts_rosterentry_import")
    response = admin_client.post(url, {"roster": upload, "year": 2027})
    assert response.status_code == 200
    assert b"SAGF-0001" in response.content
