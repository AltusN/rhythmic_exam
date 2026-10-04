from django.conf import settings
from django.db import models

from accounts.models import JudgeProfile
from exams.awards import Category
from exams.models.definition import Cycle
from exams.models.sitting import Sitting

CATEGORY_CHOICES = [(category.value, category.name) for category in Category]


class Source(models.TextChoices):
    EXAM = "EXAM", "Exam"
    IMPORTED = "IMPORTED", "Imported"


class Certification(models.Model):
    judge = models.ForeignKey(
        JudgeProfile, on_delete=models.PROTECT, related_name="certifications"
    )
    cycle = models.ForeignKey(
        Cycle, on_delete=models.PROTECT, related_name="certifications"
    )
    sitting = models.OneToOneField(
        Sitting,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="certification",
    )
    category = models.PositiveSmallIntegerField(choices=CATEGORY_CHOICES)
    examination_category = models.PositiveSmallIntegerField(
        choices=CATEGORY_CHOICES, null=True, blank=True
    )
    suggested_category = models.PositiveSmallIntegerField(
        choices=CATEGORY_CHOICES, null=True, blank=True
    )
    floor = models.PositiveSmallIntegerField(
        choices=CATEGORY_CHOICES, null=True, blank=True
    )
    cap = models.PositiveSmallIntegerField(
        choices=CATEGORY_CHOICES, null=True, blank=True
    )
    source = models.CharField(max_length=8, choices=Source.choices)
    reason = models.TextField(blank=True, default="")
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="certifications_awarded",
    )
    certified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(source=Source.EXAM) & models.Q(sitting__isnull=False)
                )
                | (models.Q(source=Source.IMPORTED) & models.Q(sitting__isnull=True)),
                name="ck_certification_source_matches_sitting",
            ),
            models.CheckConstraint(
                condition=models.Q(source=Source.EXAM) | ~models.Q(reason=""),
                name="ck_certification_imported_has_reason",
            ),
            models.CheckConstraint(
                condition=models.Q(source=Source.EXAM)
                | models.Q(
                    examination_category__isnull=True,
                    suggested_category__isnull=True,
                    floor__isnull=True,
                    cap__isnull=True,
                ),
                name="ck_certification_imported_computes_nothing",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source=Source.IMPORTED)
                    | models.Q(
                        examination_category__isnull=False,
                        suggested_category__isnull=False,
                    )
                ),
                name="ck_certification_exam_records_computed_values",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source=Source.IMPORTED)
                    | models.Q(category=models.F("suggested_category"))
                    | ~models.Q(reason="")
                ),
                name="ck_certification_departure_has_reason",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    category__range=(1, 5),
                    examination_category__range=(1, 5),
                    suggested_category__range=(1, 5),
                    floor__range=(1, 5),
                    cap__range=(1, 5),
                ),
                name="ck_certification_categories_in_range",
            ),
        ]
