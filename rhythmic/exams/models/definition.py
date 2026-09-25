from django.contrib.postgres.fields import ArrayField
from django.db import models

from questions.models import Aspect


class ExamKind(models.TextChoices):
    PRACTICAL = "PRACTICAL", "Practical"
    THEORY = "THEORY", "Theory"


class MarkingScheme(models.TextChoices):
    CHOICE = "CHOICE", "Choice"
    NUMERIC = "NUMERIC", "Numeric"


class Exam(models.Model):
    level = models.PositiveSmallIntegerField(help_text="The level of the sitting judge")
    year = models.PositiveSmallIntegerField(help_text="The year of the exam")
    kind = models.CharField(
        max_length=9, choices=ExamKind.choices, help_text="The kind of the exam"
    )

    class Meta:
        ordering = ["-year", "level", "kind"]
        constraints = [
            # This is the natural business key: each level/year/kind combination identifies
            # one exam, and the unique constraint enforces that business identity.
            models.UniqueConstraint(
                fields=["level", "year", "kind"], name="uq_one_exam_per_level_year_kind"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=ExamKind.values),
                name="ck_exam_kind_is_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year} - Level {self.level} - {self.kind}"


class ExamComponent(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="components")
    name = models.CharField(
        max_length=50,
        help_text="The name of the exam component i.e 'Apparatus Difficulty'",
    )
    position = models.PositiveSmallIntegerField(
        help_text="The position of the exam component in the exam"
    )
    marking_scheme = models.CharField(
        max_length=7,
        choices=MarkingScheme.choices,
        help_text="The marking scheme for this component",
    )
    aspect = models.CharField(
        max_length=2,
        choices=Aspect.choices,
        blank=True,
        help_text="The aspect of the exam component i.e. 'DA' or '' if theory",
    )
    difference_steps = ArrayField(
        models.DecimalField(
            max_digits=4,
            decimal_places=2,
            help_text="The difference step for this component",
        ),
        blank=True,
        default=list,
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "position"], name="uq_one_component_position_per_exam"
            ),
            models.UniqueConstraint(
                fields=["exam", "aspect"], name="uq_one_component_per_aspect_per_exam"
            ),
            models.CheckConstraint(
                condition=models.Q(marking_scheme__in=MarkingScheme.values),
                name="ck_component_marking_scheme_is_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    marking_scheme=MarkingScheme.NUMERIC, difference_steps__len__gt=0
                )
                | models.Q(
                    marking_scheme=MarkingScheme.CHOICE, difference_steps__len=0
                ),
                name="ck_component_steps_match_marking_scheme",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.exam} - {self.name} - {self.position} - {self.marking_scheme}"


class MarkingTableRow(models.Model):
    component = models.ForeignKey(
        ExamComponent, on_delete=models.CASCADE, related_name="marking_rows"
    )
    expert_minimum = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        help_text="The expert minimum for this marking table row",
    )
    percentages = ArrayField(
        models.DecimalField(
            max_digits=5,
            decimal_places=2,
            help_text="The percentage for this marking table row",
        )
    )

    class Meta:
        # load-bearing MarkingTable.__post_init__ raises ValueError if not ordered
        # because lookup walks them positively through floor_band_index
        ordering = ["expert_minimum"]
        constraints = [
            models.UniqueConstraint(
                fields=["component", "expert_minimum"],
                name="uq_one_row_per_expert_minimum_per_component",
            ),
        ]


class GradeBandRow(models.Model):
    component = models.ForeignKey(
        ExamComponent, on_delete=models.CASCADE, related_name="grade_bands"
    )
    name = models.CharField(
        max_length=50,
        help_text="The name of the grade band row i.e 'Excellent' or 'Good'",
    )
    minimum = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="The minimum value for this grade band including the lower bound",
    )

    class Meta:
        ordering = ["minimum"]
        constraints = [
            models.UniqueConstraint(
                fields=["component", "name"], name="uq_one_band_per_name_per_component"
            )
        ]


class CycleManager(models.Manager):
    def for_year(self, year: int) -> "Cycle":
        # get() rather than filter().first(): a year in no cycle, or (should an
        # official ever build an overlap) in two, must fail loudly, not pick one.
        return self.get(first_year__lte=year, last_year__gte=year)


class Cycle(models.Model):
    # FIG's four-year cycle. The retest limit, the first-cycle cap and the drop floor
    # are all counted per cycle, so it is a table rather than arithmetic on a year.
    name = models.CharField(max_length=20, unique=True)
    first_year = models.PositiveSmallIntegerField(unique=True)
    last_year = models.PositiveSmallIntegerField(unique=True)

    objects = CycleManager()

    class Meta:
        ordering = ["first_year"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(first_year__lte=models.F("last_year")),
                name="ck_cycle_ends_after_it_starts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.first_year}-{self.last_year})"


class Dimension(models.TextChoices):
    # General Judges' Rules section 2.6 grades three things; Difficulty is the mean
    # of the DA and DB components.
    DIFFICULTY = "DIFFICULTY", "Difficulty"
    EXECUTION = "EXECUTION", "Execution"
    ARTISTRY = "ARTISTRY", "Artistry"


class CategoryRequirement(models.Model):
    # One cell of the section 2.6 table: the minimum grade a dimension needs for a
    # category. Rows, not literals -- FIG republishes the table every cycle.
    cycle = models.ForeignKey(
        Cycle, on_delete=models.CASCADE, related_name="category_requirements"
    )
    category = models.PositiveSmallIntegerField()
    dimension = models.CharField(max_length=10, choices=Dimension.choices)
    minimum_grade = models.CharField(max_length=50)

    class Meta:
        ordering = ["category", "dimension"]
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "category", "dimension"],
                name="uq_one_minimum_per_category_dimension_per_cycle",
            ),
            models.CheckConstraint(
                condition=models.Q(category__gte=1, category__lte=4),
                name="ck_category_requirement_is_one_to_four",
            ),
            models.CheckConstraint(
                condition=models.Q(dimension__in=Dimension.values),
                name="ck_category_requirement_dimension_is_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Category {self.category} - {self.dimension} - {self.minimum_grade}"
