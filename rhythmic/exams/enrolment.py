"""Enrolment: a pending sitting IS the enrolment, so this is where eligibility is
enforced -- at creation, not at start_sitting, because an ineligible enrolment
should never be recorded in the first place.

Loads the inputs, asks `exams.eligibility`, and records the outcome. The rule
itself lives there and touches no database.
"""

from django.db import transaction

from accounts.models import JudgeProfile, RosterEntry
from exams.eligibility import Refusal, refusals
from exams.models import Cycle, Exam, ExamKind, Sitting, Status


class EnrolmentRefused(Exception):
    def __init__(self, refusals: list[Refusal]):
        super().__init__(", ".join(refusal.value for refusal in refusals))
        self.refusals = refusals


class JudgeHasNoProfile(Exception):
    """Not a refusal: with no sagf_id there is no roster to consult, so no override
    can make the enrolment right."""


def enrol(
    judge, exam: Exam, *, official, override_reason: str | None = None
) -> Sitting:
    # A reason of spaces is no reason: CHECK (reason <> '') would accept it.
    reason = (override_reason or "").strip()

    with transaction.atomic():
        # Locking the profile serialises enrolments for one judge, so two at once
        # cannot both count one prior sitting and both slip under the retest limit.
        try:
            profile = JudgeProfile.objects.select_for_update().get(user=judge)
        except JudgeProfile.DoesNotExist:
            raise JudgeHasNoProfile(judge) from None

        entry = RosterEntry.objects.filter(
            sagf_id=profile.sagf_id, year=exam.year
        ).first()
        cycle = Cycle.objects.for_year(exam.year)
        found = refusals(
            roster_levels=None if entry is None else entry.levels,
            exam_level=exam.level,
            prior_practical_sittings=Sitting.objects.filter(
                judge=judge,
                exam__kind=ExamKind.PRACTICAL,
                exam__year__gte=cycle.first_year,
                exam__year__lte=cycle.last_year,
            ).count(),
            has_open_sitting=Sitting.objects.filter(
                judge=judge,
                exam=exam,
                status__in=[Status.PENDING, Status.IN_PROGRESS],
            ).exists(),
            exam_is_practical=exam.kind == ExamKind.PRACTICAL,
        )
        if found and not reason:
            raise EnrolmentRefused(found)

        # An override is recorded only when there was something to override; a
        # reason on an eligible enrolment would be noise in the audit trail.
        return Sitting.objects.create(
            judge=judge,
            exam=exam,
            override_by=official if found else None,
            override_reason=reason if found else "",
        )
