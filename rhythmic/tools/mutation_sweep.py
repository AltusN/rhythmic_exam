"""Break one claim at a time and confirm a test objects.

A SURVIVED mutant is a change to the code that no test noticed — either a gap in
the suite, or a test that only appears to cover the behaviour. See CLAUDE.md,
"No test is accepted until it has been shown red".

Run from `rhythmic/`:

    ../.venv/bin/python tools/mutation_sweep.py

Nothing is committed by this script: each source file is restored in a `finally`
block, and the run ends by asserting `git status` is clean.
"""

import pathlib
import subprocess
import sys

RHYTHMIC = pathlib.Path(__file__).resolve().parent.parent
PYTHON = RHYTHMIC.parent / ".venv" / "bin" / "python"

# Cheapest first, which is the right order for a mutant with no better guess --
# pytest honours argument order and every run uses `-x`, so a mutant killed by a
# cheap file never pays for the expensive ones. Measured 2026-08-30: admin 3.9s
# and preview 2.4s, every other file 0.3-0.8s, of which 0.56s is fixed interpreter
# and Django startup shared by all of them.
#
# When `batches_for` can name the likely killer it runs that first instead, and
# this order applies to what remains. Cheapest-first optimises the wrong thing on
# its own: a mutant is only as expensive as the distance to the test that objects.
QUESTIONS_TESTS = [
    "tests/questions/test_theory.py",
    "tests/questions/test_practical.py",
    "tests/questions/test_blocks.py",
    "tests/questions/test_history.py",
    "tests/questions/test_preview.py",
    "tests/questions/test_admin.py",
]
EXAMS_TESTS = [
    "tests/exams/test_membership.py",
    "tests/exams/test_tables.py",
    "tests/exams/test_definition.py",
    "tests/exams/test_sitting.py",
    "tests/exams/test_freeze.py",
    "tests/exams/test_marking.py",
]
# Only added to the fallback, never to a per-app scope: this is the one test that
# catches model-versus-migration drift across every app, and the re-run against
# "everything" should mean that.
TEST_PATHS = EXAMS_TESTS + QUESTIONS_TESTS + ["tests/config/test_smoke.py"]

# Which tests can plausibly kill a mutant, by the app its target lives in. Scoping
# is what makes the sweep quick: an exams mutant took 6.2s against everything and
# 0.9s against tests/exams alone.
#
# Narrowing is only safe in one direction. A KILLED verdict is trustworthy whatever
# the scope -- some test objected, and that is a fact about the suite. A SURVIVED
# verdict is not: the killing test may simply not have run. So a mutant that
# survives its scope is re-run against everything before being reported, which
# costs a full run only for the rare survivor.
SCOPES = {"exams": EXAMS_TESTS, "questions": QUESTIONS_TESTS}


def batches_for(relative_path: str) -> list[list[str]]:
    """Ordered batches to run, stopping at the first that fails.

    Batch one is the test file whose name matches the mutated module, when such a
    file exists. Under `-x` what matters is reaching the killing test early, not
    running the cheap files first -- measured 2026-09-06, the six `admin-*`
    mutants each ran 46 tests that cannot fail before reaching the twelve that
    can, at roughly 4-6s apiece.

    The guess is only a guess, and correctness lives in the fallback rather than
    in it. A wrong guess costs one extra interpreter start (0.54s); a module with
    no matching test file -- `questions/models.py`, every migration -- simply
    yields none and the scope runs as before.

    The final batch is `TEST_PATHS` minus everything already run. Narrowing is
    still only safe in one direction: a KILLED verdict holds whatever the scope,
    because some test objected, while a SURVIVED verdict does not, so a mutant
    that survives its scope must still face everything else. But the tests that
    already passed cannot kill it, so re-running them proves nothing and costs
    the survivor a second full pass.
    """
    app = relative_path.split("/", 1)[0]
    scope = SCOPES.get(app)
    if scope is None:
        return [TEST_PATHS]

    # Any extension, not just .py: a template mutant in questions/templates/.../
    # preview.html is killed by tests/questions/test_preview.py.
    stem = relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    hint = f"tests/{app}/test_{stem}.py"
    batches = (
        [[hint], [path for path in scope if path != hint]]
        if hint in scope
        else [list(scope)]
    )
    already_run = {path for batch in batches for path in batch}
    return [*batches, [path for path in TEST_PATHS if path not in already_run]]


# (name, file, text to find, text to put in its place)
#
# Schema-level claims — CheckConstraint, UniqueConstraint, column types — cannot be
# mutated here. The test database is built from `questions/migrations/`, not from
# `models.py`, so renaming a constraint in the model changes nothing a test can see.
# Mutate the migration instead, or cover it with a `makemigrations --check` test.
MUTANTS = [
    (
        "ordering-apparatus",
        "questions/models.py",
        'verbose_name_plural = "apparatus"\n        ordering = ["position"]',
        'verbose_name_plural = "apparatus"',
    ),
    (
        "ordering-routine",
        "questions/models.py",
        'ordering = ["apparatus__position", "label", "pk"]',
        "ordering = []",
    ),
    (
        "ordering-routine-drop-label",
        "questions/models.py",
        'ordering = ["apparatus__position", "label", "pk"]',
        'ordering = ["apparatus__position", "pk"]',
    ),
    (
        "ordering-question",
        "questions/models.py",
        'class Meta:\n        ordering = ["reference"]',
        "class Meta:\n        ordering = []",
    ),
    (
        "ordering-contentblock",
        "questions/models.py",
        'abstract = True\n        ordering = ["position"]',
        "abstract = True\n        ordering = []",
    ),
    (
        "ondelete-routine-apparatus",
        "questions/models.py",
        "apparatus = models.ForeignKey(Apparatus, on_delete=models.PROTECT)",
        "apparatus = models.ForeignKey(Apparatus, on_delete=models.CASCADE)",
    ),
    (
        "ondelete-option-question",
        "questions/models.py",
        'Question, on_delete=models.CASCADE, related_name="options"',
        'Question, on_delete=models.DO_NOTHING, related_name="options"',
    ),
    (
        "ondelete-questionblock",
        "questions/models.py",
        'Question, on_delete=models.CASCADE, related_name="blocks"',
        'Question, on_delete=models.DO_NOTHING, related_name="blocks"',
    ),
    (
        "str-routine",
        "questions/models.py",
        'return f"{self.apparatus.name} - {self.label}"',
        'return "x"',
    ),
    (
        "str-practicalitem",
        "questions/models.py",
        'return f"{self.routine} - {self.aspect} - {self.expert_score}"',
        'return "x"',
    ),
    (
        "str-contentblock-text",
        "questions/models.py",
        'return f"{kind_display} Block at position {self.position}: '
        '{Truncator(self.text).chars(40)}"',
        'return "x"',
    ),
    (
        "admin-formset-rule",
        "questions/admin.py",
        "if correct_options != 1:",
        "if False:",
    ),
    (
        "admin-select-related",
        "questions/admin.py",
        'list_select_related = ("routine__apparatus",)',
        "",
    ),
    (
        "admin-plain-modeladmin",
        "questions/admin.py",
        "class PracticalItemAdmin(SimpleHistoryAdmin):",
        "class PracticalItemAdmin(admin.ModelAdmin):",
    ),
    (
        "admin-unregister-option",
        "questions/admin.py",
        "@admin.register(Option)\nclass OptionAdmin",
        "class OptionAdmin",
    ),
    (
        "admin-drop-option-inline",
        "questions/admin.py",
        "inlines = [QuestionBlockInline, OptionInline]",
        "inlines = [QuestionBlockInline]",
    ),
    (
        "history-off-optionblock",
        "questions/models.py",
        'Option, on_delete=models.CASCADE, related_name="blocks")\n'
        "    history = HistoricalRecords()",
        'Option, on_delete=models.CASCADE, related_name="blocks")',
    ),
    (
        # Swaps the decorator's behaviour without touching the decorator line, so
        # the substitution stays contiguous. Only a signed-in NON-staff user can
        # tell these apart: anonymous gets a 302 from either one.
        "preview-login-required-not-staff",
        "questions/views.py",
        "from django.contrib.admin.views.decorators import staff_member_required",
        "from django.contrib.auth.decorators import login_required as staff_member_required",
    ),
    (
        # Any leak works here — a printed value, a conditional class, conditional
        # markup. The test asserts two options differing only in is_correct render
        # identically, so it catches the property rather than one spelling of it.
        "preview-leaks-is-correct",
        "questions/templates/questions/preview.html",
        "<li>",
        "<li>{{ option.is_correct }}",
    ),
    (
        "admin-drop-list-filter-aspect",
        "questions/admin.py",
        'list_filter = ("aspect",)',
        "",
    ),
    (
        "ordering-exam",
        "exams/models/definition.py",
        'ordering = ["-year", "level", "kind"]',
        "ordering = []",
    ),
    (
        # Drops "year" from the key, so two exams a level apart in re-certification
        # (same level, same kind, different year) collide instead of coexisting.
        "uq-exam-level-year-kind",
        "exams/migrations/0001_initial.py",
        'fields=("level", "year", "kind"),\n                        name="uq_one_exam_per_level_year_kind",',
        'fields=("level", "kind"),\n                        name="uq_one_exam_per_level_year_kind",',
    ),
    (
        # level__gte=0 always holds for a PositiveSmallIntegerField, so this
        # disables the check regardless of what kind is actually saved.
        "ck-exam-kind-valid",
        "exams/migrations/0001_initial.py",
        'condition=models.Q(("kind__in", ["PRACTICAL", "THEORY"])),',
        'condition=models.Q(("level__gte", 0)),',
    ),
    (
        "ordering-component",
        "exams/models/definition.py",
        'ordering = ["position"]',
        "ordering = []",
    ),
    (
        # A component has no meaning without its exam. Under PROTECT the exam
        # cannot be deleted at all, so the cascade test stops seeing an empty table.
        "ondelete-component-exam",
        "exams/models/definition.py",
        'on_delete=models.CASCADE, related_name="components"',
        'on_delete=models.PROTECT, related_name="components"',
    ),
    (
        # Swaps the key onto a column the tests vary freely, so the constraint
        # still exists and still never fires.
        "uq-component-position",
        "exams/migrations/0002_examcomponent.py",
        'fields=("exam", "position"),\n                        name="uq_one_component_position_per_exam",',
        'fields=("exam", "name"),\n                        name="uq_one_component_position_per_exam",',
    ),
    (
        "uq-component-aspect",
        "exams/migrations/0002_examcomponent.py",
        'fields=("exam", "aspect"),\n                        name="uq_one_component_per_aspect_per_exam",',
        'fields=("exam", "name"),\n                        name="uq_one_component_per_aspect_per_exam",',
    ),
    (
        # position__gte=0 always holds, so the check passes whatever marking
        # scheme is stored -- including the '' Django writes for an unset field.
        "ck-component-marking-scheme",
        "exams/migrations/0002_examcomponent.py",
        '("marking_scheme__in", ["CHOICE", "NUMERIC"])',
        '("position__gte", 0)',
    ),
    (
        "ordering-markingtablerow",
        "exams/models/definition.py",
        'ordering = ["expert_minimum"]',
        "ordering = []",
    ),
    (
        "ordering-gradebandrow",
        "exams/models/definition.py",
        'ordering = ["minimum"]',
        "ordering = []",
    ),
    (
        "tables-empty-grade-bands",
        "exams/tables.py",
        "return [\n        GradeBand(name=row.name, minimum=row.minimum)\n        for row in component.grade_bands.all()\n    ]",
        "return []",
    ),
    (
        "tables-percentages-not-tuple",
        "exams/tables.py",
        "percentages=tuple(row.percentages)",
        "percentages=row.percentages",
    ),
    (
        # __gte instead of __gt lets a NUMERIC component keep an empty
        # difference_steps array, which the design says must never happen.
        "ck-component-steps-numeric",
        "exams/migrations/0005_alter_examcomponent_difference_steps_and_more.py",
        '("difference_steps__len__gt", 0), ("marking_scheme", "NUMERIC")',
        '("difference_steps__len__gte", 0), ("marking_scheme", "NUMERIC")',
    ),
    (
        "uq-row-expert-minimum",
        "exams/migrations/0004_alter_gradebandrow_minimum_and_more.py",
        'fields=("component", "expert_minimum"),\n                name="uq_one_row_per_expert_minimum_per_component",',
        'fields=("component",),\n                name="uq_one_row_per_expert_minimum_per_component",',
    ),
    (
        # question's FK carries the same PROTECT as practical_item's, so the
        # anchor must include the field name above it to hit only this one.
        "ondelete-membership-question",
        "exams/models/membership.py",
        "question = models.ForeignKey(\n        Question,\n        on_delete=models.PROTECT,",
        "question = models.ForeignKey(\n        Question,\n        on_delete=models.CASCADE,",
    ),
    (
        "uq-membership-duplicate",
        "exams/migrations/0007_componentpracticalitem_componentquestion.py",
        'fields=("component", "question"),\n                        name="uq_one_question_per_component",',
        'fields=("component", "position"),\n                        name="uq_one_question_per_component",',
    ),
    (
        "history-off-sitting",
        "exams/models/sitting.py",
        "outcome = models.CharField(max_length=255, blank=True)\n\n    history = HistoricalRecords()",
        "outcome = models.CharField(max_length=255, blank=True)",
    ),
    (
        "ondelete-sitting-judge",
        "exams/models/sitting.py",
        'settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sittings"',
        'settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sittings"',
    ),
    (
        "status-default-pending",
        "exams/models/sitting.py",
        "max_length=11, choices=Status.choices, default=Status.PENDING",
        "max_length=11, choices=Status.choices, default=Status.SUBMITTED",
    ),
    (
        # Schema-level: no such constraint exists, so this needs --create-db to
        # take effect. Only "retake the same exam" (test 2) tells this apart
        # from unique-judge-exam-sitting below.
        "unique-judge-sitting",
        "exams/migrations/0008_historicalsitting_sitting.py",
        '            options={\n                "ordering": ["exam", "started_at", "pk"],\n            },\n        ),\n    ]',
        '            options={\n                "ordering": ["exam", "started_at", "pk"],\n            },\n        ),\n        migrations.AddConstraint(\n            model_name="sitting",\n            constraint=models.UniqueConstraint(\n                fields=("judge",), name="uq_test_mutant_judge_only"\n            ),\n        ),\n    ]',
    ),
    (
        "unique-judge-exam-sitting",
        "exams/migrations/0008_historicalsitting_sitting.py",
        '            options={\n                "ordering": ["exam", "started_at", "pk"],\n            },\n        ),\n    ]',
        '            options={\n                "ordering": ["exam", "started_at", "pk"],\n            },\n        ),\n        migrations.AddConstraint(\n            model_name="sitting",\n            constraint=models.UniqueConstraint(\n                fields=("judge", "exam"), name="uq_test_mutant_judge_exam"\n            ),\n        ),\n    ]',
    ),
    (
        # Same trap as the on_delete above: ComponentPracticalItem carries an
        # identical ordering line, so the anchor needs the class header.
        "ordering-membership",
        "exams/models/membership.py",
        'class ComponentQuestion(models.Model):\n    component = models.ForeignKey(\n        ExamComponent,\n        on_delete=models.CASCADE,\n        related_name="question_members",\n    )\n    question = models.ForeignKey(\n        Question,\n        on_delete=models.PROTECT,\n        related_name="component_memberships",\n    )\n    position = models.PositiveSmallIntegerField(\n        help_text="The position of the question within the component."\n    )\n\n    class Meta:\n        ordering = ["position"]',
        'class ComponentQuestion(models.Model):\n    component = models.ForeignKey(\n        ExamComponent,\n        on_delete=models.CASCADE,\n        related_name="question_members",\n    )\n    question = models.ForeignKey(\n        Question,\n        on_delete=models.PROTECT,\n        related_name="component_memberships",\n    )\n    position = models.PositiveSmallIntegerField(\n        help_text="The position of the question within the component."\n    )\n\n    class Meta:\n        ordering = []',
    ),
    (
        # Drops the correctness filter, so the generator yields the first option
        # regardless of is_correct. Only a snapshot assertion on which option is
        # actually recorded correct catches this.
        "freeze-key-ignores-correctness",
        "exams/freeze.py",
        "(option for option in question.options.all() if option.is_correct), None",
        "(option for option in question.options.all()), None",
    ),
    (
        "freeze-empty-blocks",
        "exams/freeze.py",
        '"blocks": [_block(block) for block in question.blocks.all()],',
        '"blocks": [],',
    ),
    (
        "freeze-position-constant",
        "exams/freeze.py",
        "position=next(positions),",
        "position=1,",
    ),
    (
        "freeze-expert-score-float",
        "exams/freeze.py",
        '"expert_score": str(practical_item.expert_score),',
        '"expert_score": str(float(practical_item.expert_score)),',
    ),
    (
        # Reads sitting.status off the caller's object instead of the row the
        # select_for_update just locked -- the bug this actually shipped with,
        # found by probe rather than by a test. test_starting_an_already_started
        # _sitting_raises kills it precisely because it does NOT refresh the
        # sitting: start_sitting rebinds its local to the re-fetched row, so the
        # caller's object still reads PENDING and the second call can only raise
        # by consulting the database. Put a refresh_from_db back in that test and
        # this mutant survives.
        "freeze-guard-before-lock",
        "exams/freeze.py",
        "        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)\n"
        "        if sitting.status != Status.PENDING:\n"
        "            raise SittingAlreadyStarted()",
        "        if sitting.status != Status.PENDING:\n"
        "            raise SittingAlreadyStarted()\n"
        "        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)",
    ),
    (
        "ordering-sittingitem",
        "exams/models/sitting.py",
        'ordering = ["position", "pk"]',
        'ordering = ["-position", "pk"]',
    ),
    (
        # Passes a float where a Decimal is required. It cannot silently misprice a
        # mark -- Decimal refuses float operands outright -- so this dies on a
        # TypeError inside mark_numeric rather than on an assertion. That refusal is
        # what makes F3 unable to be quiet in this codebase.
        "marking-float-cast",
        "exams/marking.py",
        'expert = Decimal(item.marking_key["expert_score"])',
        'expert = float(item.marking_key["expert_score"])',
    ),
    (
        # Removes the catch that closes F4, so an unreadable answer escapes
        # submit_sitting as UnparseableAnswer -- exactly the legacy crash, on exactly
        # the legacy input. Killed by test_an_unreadable_numeric_response_scores_zero.
        "marking-no-unparseable-catch",
        "exams/marking.py",
        """                try:
                    item.percentage = mark_numeric(response, expert, table)
                except UnparseableAnswer:
                    item.percentage = Decimal("0")  # F4""",
        "                item.percentage = mark_numeric(response, expert, table)",
    ),
    (
        # Marks against the live component instead of the table frozen into the item,
        # which is the whole of the 2026-09-08 decision. Only
        # test_the_mark_uses_the_table_frozen_at_start_of_sitting can see it: every
        # other test edits the table AFTER submission, when the live and frozen tables
        # still agree. That test's positive control is load-bearing -- with its filter
        # matching no rows, this mutant survives again.
        "marking-uses-live-table",
        "exams/marking.py",
        '                table = marking_table_from_json(item.marking_key["marking_table"])',
        "                table = build_marking_table(\n"
        "                    sitting.exam.components.get(position=item.component_position)\n"
        "                )",
    ),
    (
        # Reads sitting.status through item.sitting -- a related object Django caches
        # on the instance after first access -- instead of the row just locked. This
        # was shipped and found by probe on 2026-09-12: a submitted sitting accepted a
        # further response, because the cached Sitting still said IN_PROGRESS. The
        # third appearance of "the object in memory is not the row".
        "record-guard-reads-cached-fk",
        "exams/marking.py",
        """        sitting = Sitting.objects.select_for_update().get(pk=item.sitting_id)
        if sitting.status != Status.IN_PROGRESS:
            raise SittingNotInProgress("Sitting is not in progress.")""",
        """        if item.sitting.status != Status.IN_PROGRESS:
            raise SittingNotInProgress("Sitting is not in progress.")
        sitting = Sitting.objects.select_for_update().get(pk=item.sitting_id)""",
    ),
    (
        # Drops the guard, so a sitting can be submitted twice and every mark is
        # recomputed and rewritten. Killed by test_submitting_twice_raises_an_exception.
        "submit-guard-removed",
        "exams/marking.py",
        """        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)
        if sitting.status != Status.IN_PROGRESS:
            raise SittingNotInProgress("Sitting is not in progress.")
""",
        "        sitting = Sitting.objects.select_for_update().get(pk=sitting.pk)\n",
    ),
    (
        # Sends choice items down the numeric branch and vice versa. Kills eight tests,
        # so it proves little on its own -- it is here because a branch with no mutant
        # is a branch nobody has confirmed is reached.
        "marking-scheme-branch-swapped",
        "exams/marking.py",
        "            if item.marking_scheme == MarkingScheme.CHOICE:",
        "            if item.marking_scheme != MarkingScheme.CHOICE:",
    ),
]

HISTORY_TAILS = {
    "question": 'blank=True, help_text="Internal notes or context for the question."',
    "practicalitem": 'max_digits=4, decimal_places=2, help_text="Expert score for this item."',
    "option": 'default=False, help_text="Indicates if this option is the correct answer."',
}
for model, tail in HISTORY_TAILS.items():
    MUTANTS.append(
        (
            f"history-off-{model}",
            "questions/models.py",
            f"{tail}\n    )\n    history = HistoricalRecords()",
            f"{tail}\n    )",
        )
    )


def run_tests(paths: list[str], *, fresh_database: bool) -> int:
    """Run `paths` once. `fresh_database` rebuilds the test database first.

    `--reuse-db` keeps the sweep fast, but pytest-django then never re-applies
    migrations, so a mutated migration is invisible and its mutant is reported
    SURVIVED when the tests would in fact have killed it. Any mutant that edits a
    migration must therefore pay for `--create-db`.
    """
    result = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "pytest",
            *paths,
            "-q",
            "-x",
            "--no-header",
            "--create-db" if fresh_database else "--reuse-db",
            "-p",
            "no:cacheprovider",
        ],
        cwd=RHYTHMIC,
        capture_output=True,
        text=True,
    )
    return result.returncode


def main() -> int:
    survived, unapplied = [], []
    for name, relative_path, before, after in MUTANTS:
        source = RHYTHMIC / relative_path
        original = source.read_text()
        if before not in original:
            unapplied.append(name)
            print(f"{'UNAPPLIED':9s} {name:34s} pattern not found")
            continue
        try:
            source.write_text(original.replace(before, after, 1))
            fresh = "migrations" in relative_path
            returncode = 0
            for batch in batches_for(relative_path):
                if not batch:
                    continue
                returncode = run_tests(batch, fresh_database=fresh)
                if returncode != 0:
                    break
        finally:
            source.write_text(original)
        if returncode == 0:
            survived.append(name)
        print(f"{'SURVIVED' if returncode == 0 else 'KILLED':9s} {name}")

    mutated_paths = sorted({relative for _, relative, _, _ in MUTANTS})
    dirty = subprocess.run(
        ["git", "status", "--short", *mutated_paths],
        cwd=RHYTHMIC,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print(f"\nWARNING: working tree is not clean after the sweep:\n{dirty}")

    print(
        f"\nkilled={len(MUTANTS) - len(survived) - len(unapplied)} survived={len(survived)}"
    )
    for name in survived:
        print(f"  SURVIVED  {name}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
