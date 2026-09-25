from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models
from simple_history.models import HistoricalRecords


class User(AbstractUser):
    pass


class JudgeProfile(models.Model):
    # Nullable: the category import creates judges before they have ever signed in,
    # and sign-in attaches the user later. Postgres treats NULLs as distinct, so the
    # one-to-one stays unique among linked profiles while unlinked ones coexist.
    # PROTECT: deleting a login must never delete a judge's history.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="judge_profile",
    )
    sagf_id = models.CharField(max_length=20, unique=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["sagf_id"]

    def __str__(self) -> str:
        return self.sagf_id


class RosterEntry(models.Model):
    # Matched to a judge by sagf_id VALUE, not a foreign key: SAGF's roster exists
    # before the judge has an account or a profile.
    sagf_id = models.CharField(max_length=20)
    email = models.EmailField()
    year = models.PositiveSmallIntegerField()
    levels = ArrayField(models.PositiveSmallIntegerField())

    history = HistoricalRecords()

    class Meta:
        ordering = ["-year", "sagf_id"]
        verbose_name_plural = "roster entries"
        constraints = [
            models.UniqueConstraint(
                fields=["sagf_id", "year"],
                name="uq_one_roster_entry_per_judge_per_year",
            ),
        ]

    def save(self, *args, **kwargs):
        # Here rather than in the import alone: sign-in matches Google's verified
        # address against this column, and an admin edit must not store a casing
        # the match then misses.
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.sagf_id} - {self.year}"
