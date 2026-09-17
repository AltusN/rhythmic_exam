from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from exams.models import ComponentResult, MarkingScheme, Sitting, SittingItem, Status
from exams.tables import (
    grade_bands_from_json,
    marking_table_from_json,
)
from scoring.aggregate import grade, score_component
from scoring.marking import mark_choice, mark_numeric
from scoring.values import UnparseableAnswer


class SittingNotInProgress(Exception):
    pass


def record_response(item: SittingItem, response: str) -> None:
    with transaction.atomic():
        sitting = Sitting.objects.select_for_update().get(pk=item.sitting_id)
        if sitting.status != Status.IN_PROGRESS:
            raise SittingNotInProgress("Sitting is not in progress.")
        item.response = {"answer": response}
        item.save(update_fields=["response"])


def submit_sitting(sitting: Sitting) -> None:
    with transaction.atomic():
        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)
        if sitting.status != Status.IN_PROGRESS:
            raise SittingNotInProgress("Sitting is not in progress.")

        groups = defaultdict(list)

        for item in sitting.items.all():
            # Unanswered scores 0: the candidate sat the component and did not answer.
            # Categorically different from F10's absent component, which has no sitting
            # and therefore no items at all.
            response = item.response["answer"] if item.response else None

            if item.marking_scheme == MarkingScheme.CHOICE:
                item.percentage = mark_choice(
                    response, item.marking_key["correct_option"]
                )
            else:
                expert = Decimal(item.marking_key["expert_score"])
                table = marking_table_from_json(item.marking_key["marking_table"])
                try:
                    item.percentage = mark_numeric(response, expert, table)
                except UnparseableAnswer:
                    item.percentage = Decimal("0")  # F4

            item.save(update_fields=["percentage"])
            groups[item.component_name].append(item)

        results = []
        for component_name, group in groups.items():
            percentage = score_component([item.percentage for item in group])
            results.append(
                ComponentResult(
                    sitting=sitting,
                    component_name=component_name,
                    component_position=group[0].component_position,
                    percentage=percentage,
                    grade_name=grade(
                        percentage=percentage,
                        bands=grade_bands_from_json(group[0].grade_bands),
                    ),
                )
            )
        ComponentResult.objects.bulk_create(results)

        sitting.status = Status.SUBMITTED
        sitting.submitted_at = timezone.now()
        sitting.save(update_fields=["status", "submitted_at"])
