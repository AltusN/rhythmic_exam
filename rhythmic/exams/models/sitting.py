import secrets

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from exams.models import Exam


class Status(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    SUBMITTED = "SUBMITTED", "Submitted"
    CERTIFIED = "CERTIFIED", "Certified"


def new_candidate_number() -> str:
    return secrets.token_hex(4).upper()


class Sitting(models.Model):
    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sittings"
    )
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="sittings")
    # a sitting that exists but has not started can only have the status PENDING
    status = models.CharField(
        max_length=11, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    certified_at = models.DateTimeField(null=True, blank=True)
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="certifications_made",
    )
    outcome = models.CharField(max_length=255, blank=True)
    # What the certifying official sees instead of a name (General Judges' Rules
    # section 2.2.1: results reviewed "by judge number not name"). Not the pk, which
    # is sequential and would reveal the order of enrolment.
    candidate_number = models.CharField(max_length=8, default=new_candidate_number)
    # Set only when an official enrolled a judge despite a refusal.
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="overrides_made",
    )
    override_reason = models.TextField(blank=True, default="")

    history = HistoricalRecords()

    class Meta:
        ordering = ["exam", "started_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "candidate_number"],
                name="uq_one_candidate_number_per_exam",
            ),
            # Both or neither. A blank reason is worse than none: it looks like an
            # audit trail without being one.
            models.CheckConstraint(
                condition=models.Q(override_by__isnull=True, override_reason="")
                | (models.Q(override_by__isnull=False) & ~models.Q(override_reason="")),
                name="ck_sitting_override_has_official_and_reason",
            ),
        ]

    def __str__(self) -> str:
        if self.certified_by:
            return f"{self.exam} - {self.judge} - {self.status} - Certified by {self.certified_by}"
        return f"{self.exam} - {self.judge} - {self.status}"


class SittingItem(models.Model):
    sitting = models.ForeignKey(Sitting, on_delete=models.CASCADE, related_name="items")
    component_name = models.CharField(max_length=50)
    component_position = models.PositiveSmallIntegerField()
    marking_scheme = models.CharField(max_length=7)
    position = models.PositiveSmallIntegerField()
    question_snapshot = models.JSONField()
    marking_key = models.JSONField()
    grade_bands = models.JSONField()
    response = models.JSONField(null=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["sitting", "position"], name="uq_one_item_position_per_sitting"
            )
        ]

    def __str__(self) -> str:
        return f"{self.component_name} - {self.position}"


class ComponentResult(models.Model):
    sitting = models.ForeignKey(
        Sitting, on_delete=models.CASCADE, related_name="results"
    )
    component_name = models.CharField(max_length=50)
    component_position = models.PositiveSmallIntegerField()
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade_name = models.CharField(max_length=50)

    class Meta:
        ordering = ["component_position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["sitting", "component_name"],
                name="uq_one_result_per_component_per_sitting",
            )
        ]

    def __str__(self) -> str:
        return f"{self.component_name} - {self.percentage}"
