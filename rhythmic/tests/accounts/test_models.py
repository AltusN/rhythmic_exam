import pytest
from django.db import IntegrityError, transaction

from accounts.models import JudgeProfile, RosterEntry


@pytest.mark.django_db
def test_a_judge_profile_needs_no_user():
    # The category import creates judges before they have ever signed in.
    profile = JudgeProfile.objects.create(user=None, sagf_id="SAGF-0001")

    assert JudgeProfile.objects.get(pk=profile.pk).user_id is None


@pytest.mark.django_db
def test_two_profiles_without_users_coexist():
    JudgeProfile.objects.create(user=None, sagf_id="SAGF-0001")
    JudgeProfile.objects.create(user=None, sagf_id="SAGF-0002")

    assert JudgeProfile.objects.filter(user__isnull=True).count() == 2


@pytest.mark.django_db
def test_a_user_has_at_most_one_profile(django_user_model):
    user = django_user_model.objects.create_user(username="judge", password="x")
    JudgeProfile.objects.create(user=user, sagf_id="SAGF-0001")

    with pytest.raises(IntegrityError), transaction.atomic():
        JudgeProfile.objects.create(user=user, sagf_id="SAGF-0002")


@pytest.mark.django_db
def test_a_judge_appears_once_per_roster_year():
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2026, levels=[1]
    )
    RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="a@example.com", year=2027, levels=[1]
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        RosterEntry.objects.create(
            sagf_id="SAGF-0001", email="a@example.com", year=2026, levels=[2]
        )


@pytest.mark.django_db
def test_a_roster_email_is_stored_lowercase():
    entry = RosterEntry.objects.create(
        sagf_id="SAGF-0001", email="Judge@Example.COM", year=2026, levels=[1]
    )

    # Re-read the row: lowercasing only the instance would pass an in-memory check.
    assert RosterEntry.objects.get(pk=entry.pk).email == "judge@example.com"
