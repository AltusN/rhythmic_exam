from itertools import count

from django.db import transaction
from django.utils import timezone

from exams.models import Sitting, SittingItem, Status
from exams.tables import (
    build_grade_bands,
    build_marking_table,
    grade_bands_as_json,
    marking_table_as_json,
)


class SittingAlreadyStarted(Exception):
    pass


class QuestionHasNoAnswer(Exception):
    pass


class ComponentHasNoGradeBands(Exception):
    pass


def _block(block):
    return {
        "kind": block.kind,
        "position": block.position,
        "text": block.text,
        "image": block.image.name,
        "video": block.video.name,
    }


def _frozen_question(question) -> tuple[dict, dict]:
    question_snapshot = {
        "reference": question.reference,
        "blocks": [_block(block) for block in question.blocks.all()],
        "options": [
            {
                "position": option.position,
                "blocks": [_block(block) for block in option.blocks.all()],
            }
            for option in question.options.all()
        ],
    }
    correct_option = next(
        (option for option in question.options.all() if option.is_correct), None
    )
    if correct_option is None:
        raise QuestionHasNoAnswer(question.reference)
    marking_key = {
        "correct_option": str(correct_option.position),
    }
    return question_snapshot, marking_key


def _frozen_practical_item(practical_item, marking_table) -> tuple[dict, dict]:
    practical_item_snapshot = {
        "routine": {
            "apparatus": {
                "name": practical_item.routine.apparatus.name,
                "position": practical_item.routine.apparatus.position,
            },
            "label": practical_item.routine.label,
            "video": practical_item.routine.video.name,
        },
        "aspect": practical_item.aspect,
    }
    marking_key = {
        "expert_score": str(practical_item.expert_score),
        "marking_table": marking_table,
    }
    return practical_item_snapshot, marking_key


def start_sitting(sitting: Sitting) -> None:
    with transaction.atomic():
        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)
        if sitting.status != Status.PENDING:
            raise SittingAlreadyStarted()

        positions = count(1)
        items = []

        for component in sitting.exam.components.prefetch_related(
            "marking_rows", "grade_bands"
        ):
            practical_members = component.practical_item_members.select_related(
                "practical_item__routine__apparatus"
            )
            table_json = None
            if practical_members:
                table_json = marking_table_as_json(build_marking_table(component))
            bands_json = grade_bands_as_json(build_grade_bands(component))
            if not bands_json:
                raise ComponentHasNoGradeBands(component.name)
            frozen = [
                _frozen_question(membership.question)
                for membership in component.question_members.select_related(
                    "question"
                ).prefetch_related(
                    "question__blocks", "question__options", "question__options__blocks"
                )
            ] + [
                _frozen_practical_item(membership.practical_item, table_json)
                for membership in practical_members
            ]

            for question_snapshot, marking_key in frozen:
                items.append(
                    SittingItem(
                        sitting=sitting,
                        component_name=component.name,
                        component_position=component.position,
                        component_aspect=component.aspect,
                        marking_scheme=component.marking_scheme,
                        grade_bands=bands_json,
                        position=next(positions),
                        question_snapshot=question_snapshot,
                        marking_key=marking_key,
                    )
                )
        SittingItem.objects.bulk_create(items)
        sitting.started_at = timezone.now()
        sitting.status = Status.IN_PROGRESS
        sitting.save()
