from django.db import transaction

from accounts.models import User
from exams.awards import (
    AspectResult,
    Category,
    PriorCertification,
    award_bounds,
    dimension_grades,
    examination_category,
)
from exams.models import Certification, Cycle, ExamKind, Sitting, Source, Status
from exams.tables import grade_bands_from_json
from questions.models import Aspect


class SittingNotSubmitted(Exception):
    pass


class NotAPracticalSitting(Exception):
    pass


class ResultsIncomplete(Exception):
    pass


def certify(sitting: Sitting, *, official: User, category: Category, reason: str = ""):
    with transaction.atomic():
        # Read the record from the database to ensure we have the latest state
        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)
        if sitting.status != Status.SUBMITTED:
            raise SittingNotSubmitted()
        if sitting.exam.kind != ExamKind.PRACTICAL:
            raise NotAPracticalSitting()

        missing = set(Aspect.values) - set(
            sitting.results.values_list("aspect", flat=True)
        )
        if missing:
            raise ResultsIncomplete(
                f"Missing results for aspects: {', '.join(sorted(missing))}"
            )
        # At this point, all results are present, and the sitting can be certified.

        results = {}
        for result in sitting.results.all():
            # Process each result as needed for certification
            item = sitting.items.filter(component_aspect=result.aspect).first()
            bands = tuple(grade_bands_from_json(item.grade_bands))
            results[result.aspect] = AspectResult(
                percentage=result.percentage, grade=result.grade_name, bands=bands
            )

        dimensions = dimension_grades(results)

        cycle = Cycle.objects.for_year(sitting.exam.year)

        requirements = {
            (row.category, row.dimension): row.minimum_grade
            for row in cycle.category_requirements.all()
        }

        examination = examination_category(dimensions, requirements)

        profile = sitting.judge.judge_profile
        history = [
            PriorCertification(
                cycle_first_year=prior.cycle.first_year,
                category=Category(prior.category),
            )
            for prior in profile.certifications.select_related("cycle").order_by("pk")
        ]
        previous = (
            Cycle.objects.filter(last_year__lt=cycle.first_year)
            .order_by("-first_year")
            .first()
        )

        bounds = award_bounds(
            examination=examination,
            history=history,
            cycle_first_year=cycle.first_year,
            previous_cycle_first_year=previous.first_year if previous else None,
        )

        certification = Certification.objects.create(
            judge=profile,
            cycle=cycle,
            sitting=sitting,
            source=Source.EXAM,
            category=category,
            examination_category=examination,
            suggested_category=bounds.suggested,
            floor=bounds.floor,
            cap=bounds.cap,
            reason=reason.strip(),
            certified_by=official,
        )

        sitting.status = Status.CERTIFIED
        sitting.save(update_fields=["status"])

        return certification
