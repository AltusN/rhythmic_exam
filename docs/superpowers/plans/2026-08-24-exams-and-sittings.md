# Exams and Sittings Implementation Plan

**Goal:** Define what an exam *is* — a dated, levelled set of components each owning an
ordered set of questions — and record what a candidate *did* — a sitting whose items are
frozen at start and whose marks are stored, never recomputed.

**Architecture:** Two halves. Part A is the exam definition: `Exam`, `ExamComponent`, the
marking tables and grade bands as rows, and explicit membership through-models. Part B is
the sitting: enrolment as a pending sitting, a freeze at start that copies question content
into JSONB, responses, and marking at submission through `scoring/`. Part A is independently
shippable — after Task 5 an official can define a level 2 theory exam and see exactly which
75 questions it contains, with no sitting anywhere.

**Tech Stack:** Django 6.1, Postgres 17, `pytest-django`, `django-simple-history`, ruff.
`scoring/` is consumed as a plain library and imports nothing from Django.

**Spec:** `docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md` — the
*Exams and sittings*, *Scoring* and *Findings* sections. Read F1, F5, F9, F10, F11 and F12
before starting; five of the ten tasks exist to close one of them.

**Working agreement:** `CLAUDE.md` governs. Altus writes every line of implementation code
and every test. This plan names files, constructs and decisions; it does not contain
finished implementations, and the steps that look like they want code are prompts to write
it. Each task ends at a review gate: post the code, Claude reviews *and mutates* before the
next task starts.

## Global constraints

- **`rhythmic/scoring/` imports nothing from Django and touches no database.** The exams app
  depends on `scoring/`, never the reverse. Enforced by ruff `TID251`.
- **`Decimal` everywhere for marks, scores and deductions. Never `float`. Never compare
  answers as strings** — F3.
- **Marking tables and grade bands are data, never literals in Python.** FIG republishes
  them every four-year cycle.
- **No real exam content in this repository.** Fixtures are synthetic.
- **No test is accepted until it has been shown red.** Twelve vacuous assertions so far.
  Claude mutates and reports at every review gate.
- **Run `../.venv/bin/python tools/mutation_sweep.py` at the end of every task**, and add
  that task's claims to the catalogue as part of it.
- Commit messages follow Conventional Commits with the closed scope set; this app's scope
  is `exams`. Cite the finding: `fix(exams): select questions by membership, not level (F9)`.

## What this plan deliberately leaves out

- **Eligibility, roster and certification.** `RosterEntry`, `Certification` and the
  level-versus-attempt distinction are the accounts plan. This plan's `Sitting.judge` points
  at `settings.AUTH_USER_MODEL`, and `JudgeProfile` is a `OneToOneField` to that same user
  in the accounts plan — so the foreign key never has to move.

  **Nothing registers judges yet.** Until the accounts plan lands, users come from
  `manage.py createsuperuser` or the admin, and tests use `django_user_model.objects.create_user(...)`.
  Registration itself inverts the legacy flow: an official imports the SAGF roster, a
  candidate signs in with Google, and the system matches the verified email against the
  roster. No match, no entry.

  **This ordering is deliberate and the dependency is why.** The spec's `Certification`
  carries `judge · level · awarded_on · sitting · certified_by` — it points *at* a sitting.
  Accounts depends on exams; build accounts first and that foreign key has nothing to
  reference. Part A here needs no user at all.

  **The cost, stated plainly: this app cannot enforce eligibility.** The spec requires that
  a judge may sit an exam only if this year's roster permits that level *and* their
  certification history supports it, with disagreements flagged to an official and any
  override recording who made it and why. None of that exists here — a `Sitting` can be
  created for any user against any exam. **The check belongs at sitting *creation*, in the
  accounts plan**, not at `start_sitting`, because a pending sitting is the enrolment and an
  ineligible enrolment should never be recorded in the first place.
- **The overall category.** Four grades to one category is the rule in the spec's §2.6
  table. It needs all four aspect grades to exist first, which is Task 9's output.
- **The candidate-facing runner.** The React island is the last plan. Part B produces the
  models and the marking; the screens come later.
- **Certification.** `certified_at` / `certified_by` / `outcome` are fields on `Sitting`
  from Task 6, and nothing writes them here. Scoring and certification are separate events
  by design.

---

## File structure

```
rhythmic/exams/
  models/            split by lifecycle, because that is the whole argument of this app
    __init__.py        re-exports; INSTALLED_APPS sees one app
    definition.py      Exam, ExamComponent, MarkingTableRow, GradeBandRow  — edited
    membership.py      ComponentQuestion, ComponentPracticalItem           — edited
    sitting.py         Sitting, SittingItem, ComponentResult               — recorded
  tables.py          builds scoring.MarkingTable / GradeBand from rows
  freeze.py          start_sitting() — the snapshot
  marking.py         submit_sitting() — calls scoring/, stores what comes back
  admin.py
rhythmic/tests/exams/
  __init__.py            required — see the note under Layout in CLAUDE.md
  test_definition.py     test_membership.py  test_sitting.py
  test_tables.py         test_freeze.py      test_marking.py
  test_results.py        test_admin.py
```

**Why `models/` is a package here and a single file in `questions/`.** The questions app has
one lifecycle — content that is edited. This app has two, and the boundary between them is
the design: `definition.py` and `membership.py` hold rows officials change; `sitting.py`
holds rows that must never change after they are written. A reviewer should be able to see
that boundary in the file list. If it turns out to be one flat file's worth of code by Task
6, collapse it and say so — this is a prediction, not a commitment.

---

# Part A — the exam definition

## Task 1: Create the `exams` app and wire it in

**Files:**
- Create: `exams/` (via `startapp`), `exams/models/__init__.py`
- Modify: `config/settings.py`
- Test: `tests/exams/test_definition.py`

**Interfaces:**
- Produces: an installed app labelled `exams`.

- [ ] **Step 1: Generate the app**

`manage.py startapp exams` from `rhythmic/`. Then turn `models.py` into the package the
file structure above describes — delete `models.py`, create `models/__init__.py`. Delete
the generated `tests.py`; tests live in `rhythmic/tests/exams/`, which needs an
`__init__.py`.

- [ ] **Step 2: Register it**

Add `"exams"` to `INSTALLED_APPS` in `config/settings.py`, after `"questions"`.

- [ ] **Step 3: Write the failing test**

One test asserting the app is installed and its label is `exams`. The construct is
`django.apps.apps.get_app_config("exams")`, which raises `LookupError` when it is not.

Do not assert on `INSTALLED_APPS` itself — that reads back the setting you just wrote and
is the first disguise.

- [ ] **Step 4: Run it red, then green**

Red before Step 2's edit, green after. If you have already made the edit, comment it out to
see red; a test never shown red is not accepted here.

- [ ] **Step 5: Full suite, lint, commit**

```bash
../.venv/bin/python -m pytest -q && ../.venv/bin/ruff format . && ../.venv/bin/ruff check .
git status --short
git commit
```

Subject: `feat(exams): add the exams app`

**Review gate.** Claude checks the app label and that `models/` is a package Django can
import.

---

## Task 2: `Exam` — level, year, kind

**Files:**
- Create: `exams/models/definition.py`, `exams/migrations/0001_initial.py` (generated)
- Modify: `exams/models/__init__.py`
- Test: `tests/exams/test_definition.py`

**Interfaces:**
- Produces: `Exam(level, year, kind)`; `ExamKind.THEORY`, `ExamKind.PRACTICAL` as a
  `TextChoices`. **Named `ExamKind`, not `Kind`** — `questions.models.Kind` already exists
  and means `TEXT|IMAGE|VIDEO`. Two `Kind` classes one import apart is how a content block
  ends up compared against `THEORY`, and the comparison would simply be false rather than
  raising.

**The decision this task encodes.** `Exam` carries a **year**, and that single field is the
fix for **F11**. Legacy's `exam_result` declared `UNIQUE (sagf_id)` with no year and no
attempt number, so one row per person was the schema's ceiling and a recertification had
nowhere to go. Re-certification is a requirement, so sittings accumulate against a judge and
each points at a dated exam.

**Theory and practical are separate exams, not components of one** — decided 2026-08-08 and
re-argued in `CLAUDE.md`. That is what makes **F10 unrepresentable** rather than guarded: a
candidate who did not sit the practical has no practical sitting, so there is no field for a
fabricated `"0"` to occupy and no `practical_taken` flag for a future reader to forget.

- [ ] **Step 1: Write the model**

`level` a `PositiveSmallIntegerField`. `year` a `PositiveSmallIntegerField` — not a
`DateField`; an exam belongs to a certification year, not to a day. `kind` a `CharField`
with `choices=ExamKind.choices`, **no default** — the same argument as
`PracticalItem.aspect` in Task 3 of the questions plan: a default here silently makes
everything theory.

**But no default is not the whole guard, and `PracticalItem.aspect` is a weaker precedent
than this sentence implies** — it permits `aspect=''` today. **Resolved 2026-08-25: `kind`
also carries a `CheckConstraint`**, `models.Q(kind__in=ExamKind.values)`, named
`ck_exam_kind_is_valid`, in `Meta.constraints` beside the `UniqueConstraint`. See **How
`kind` is pinned** under Step 3 for why a default was never the whole question.

`Meta.ordering` — a total order, so no tie is left to the planner. `["-year", "level",
"kind"]` leaves ties when two exams share all three, which the constraint below forbids, so
this one is genuinely total. Say so in a comment rather than adding `pk` reflexively.

`Meta.constraints` — a `UniqueConstraint` on `("level", "year", "kind")`, named
`uq_one_exam_per_level_year_kind`.

- [ ] **Step 2: Migrate and read the DDL**

```bash
../.venv/bin/python manage.py makemigrations exams
../.venv/bin/python manage.py sqlmigrate exams 0001
```

Confirm `smallint NOT NULL` on `year`, `varchar` with no `DEFAULT` on `kind`, and a named
`UNIQUE (level, year, kind)`, and a named `CHECK` on `kind`. Note what the absent `DEFAULT`
does and does not buy you: Django still writes
`''` for an unset `kind`, so the DDL confirms only that nothing was defaulted, never that
nothing empty can be stored. Django's optimizer folds `AddConstraint` into `CreateModel`
when both are in one migration, so a missing operation is not a missing constraint.

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_two_exams_can_share_a_level_across_years` | 2026 and 2030 level 2 theory both save |
| `test_a_duplicate_level_year_kind_is_refused` | `pytest.raises(IntegrityError)`, `match="uq_one_exam_per_level_year_kind"` |
| `test_kind_is_not_silently_theory` | `pytest.raises(IntegrityError)`, `match="ck_exam_kind_is_valid"` on `Exam.objects.create(level=1, year=2026)` |
| `test_exams_are_ordered_newest_year_first` | assert on the **bare queryset**, never `.order_by(...)` |

Match on the **constraint name only**, never Postgres's full sentence — the wording is
Postgres's and will change.

The first test is the F11 marker: name it so a reader knows why it exists.

**How `kind` is pinned. Resolved 2026-08-25: a `CheckConstraint`.** This plan originally
specified `test_kind_has_no_default` as *"building `Exam(level=1, year=2026)` and saving
raises rather than quietly storing theory."* **That test cannot pass, and the claim behind
it is wrong.** Probed 2026-08-25 against the precedent this plan cites,
`PracticalItem.aspect` — a `CharField` with `choices` and no default — saved with no aspect
supplied at all:

```
>>> STORED aspect = ''  (save did NOT raise)
```

`blank=False` governs forms and `full_clean()`; `save()` never consults it. Django gives an
unset `CharField` its empty-string default, and Postgres accepts `''` into a
`varchar NOT NULL`. **`choices=` generates no DDL** — it constrains the admin and validation
only, so nothing at the schema level refuses a row.

The distinction to hold: *no default* and *cannot be saved empty* are different claims.
`default=` decides what gets filled in; only a database constraint decides what gets
refused. And an `Exam` with `kind=''` is a third kind of exam that no code branches on —
the same family as F10, a state the schema permits and the domain does not have.

**Chosen: option 1**, because `ContentBlock` already constrains its own `kind` in the
database, so this is the precedent here rather than a new idea — and `Exam.kind` is the
field the whole theory/practical split rests on.

1. **Add a `CheckConstraint`** that `kind` is one of the choices — `models.Q(kind__in=
   ExamKind.values)`, named `ck_exam_kind_is_valid`. The test then asserts
   `pytest.raises(IntegrityError, match="ck_exam_kind_is_valid")`, Step 2 gains a `CHECK`
   clause to confirm, and the bad row is unrepresentable rather than merely undefaulted.
   Precedent exists: `ContentBlock` already constrains its own `kind` in the database.
2. *(Not taken.)* **Keep it undefaulted** and assert the stored value is `""`. Not
   vacuous — it goes red if anyone adds `default=ExamKind.THEORY` — but it pins the absence
   of a default rather than the impossibility of a bad row.

Note `PracticalItem.aspect` has this same hole today: `aspect=''` is storable. Out of scope
for this task; record it as a finding if it is confirmed to matter.

- [ ] **Step 4: Run red, then implement, then green**

The ordering test needs years and levels arranged so that creation order disagrees with the
expected order, or it passes with `Meta.ordering` deleted. Task 8 of the questions plan cost
two rounds on exactly this.

- [ ] **Step 5: Sweep, lint, commit**

Add `ordering-exam` and `uq-exam-level-year-kind` to `tools/mutation_sweep.py`, and add
`tests/exams/test_definition.py` to its `TEST_PATHS`.

Subject: `feat(exams): add Exam with a certification year (F11)`
Body: that the year is what makes recertification representable, and that legacy's
`UNIQUE (sagf_id)` could hold one result per person for all time.

**Review gate.** Claude runs the sweep and reports whether both new mutants die.

---

## Task 3: `ExamComponent` — one per marked section

**Files:**
- Modify: `exams/models/definition.py`, `exams/models/__init__.py`
- Test: `tests/exams/test_definition.py`

**Interfaces:**
- Consumes: `Exam` from Task 2.
- Produces: `ExamComponent(exam, name, position, marking_scheme, aspect)`;
  `MarkingScheme.CHOICE`, `MarkingScheme.NUMERIC`.

**Why this model and not a `Paper`.** The spec already defines `ExamComponent` as "one per
marked section of the exam", carrying its own grade bands and its own marking table — which
is exactly the thing that should own a set of questions. Theory is **one** component holding
choice questions; the practical is **four**, one per aspect, holding five numeric questions
each. One mechanism for both halves of the exam rather than papers for theory and components
for the practical.

- [ ] **Step 1: Write the model**

`exam` a `ForeignKey` with `on_delete=models.CASCADE` and `related_name="components"` — a
component has no meaning without its exam, the same argument as `Option` under `Question`.

`name` a `CharField` — what a candidate sees on their result. `position` a
`PositiveSmallIntegerField`. `marking_scheme` a `CharField` with `choices`, no default,
**and a `CheckConstraint`** — `models.Q(marking_scheme__in=MarkingScheme.values)`, named
`ck_component_marking_scheme_is_valid` (decided 2026-08-27, same argument as
`ck_exam_kind_is_valid` in Task 2: `choices=` generates no DDL, so without a check Django
writes `''` and Postgres accepts it). Task 4 builds a marking table off this field, so a
component that is neither `CHOICE` nor `NUMERIC` is a component nothing can mark.

`aspect` a `CharField` using **`questions.models.Aspect.choices`**, `blank=True` for theory,
and **deliberately no check constraint** — `''` is a legitimate aspect here, because theory
has none. Note the asymmetry with the field above it: on `marking_scheme` blank is a bug, on
`aspect` blank is meaningful, and they sit two lines apart. Any check on `aspect` would have
to read `aspect__in=Aspect.values` **or** `aspect=""`, which is why the partial unique index
below carries `condition=~Q(aspect="")` rather than the field carrying a check.
Store it rather than inferring it from the members' aspects: apparatus and aspect are
independent dimensions read *both* ways, and `CLAUDE.md` records that ordering and inference
are what drift. A component that knows it is `DA` is a lookup; one that infers it is a scan
that can disagree with itself.

`Meta.constraints`: `UniqueConstraint(("exam", "position"))` named
`uq_one_component_position_per_exam`, and `UniqueConstraint(("exam", "aspect"))` named
`uq_one_component_per_aspect_per_exam`. Plain constraints, both of them.

**Corrected 2026-08-27. This step used to specify `condition=~Q(aspect="")` on the second
one, and that was wrong.** The stated reason was that "the theory components across several
exams collide on the empty string" — they do not. `exam` is *in* the key, so two rows
differing by exam differ as tuples whatever `aspect` holds. Verified with two probes against
the constraint as written, with no condition:

| probe | result |
|---|---|
| blank-aspect components in **different exams** | both save |
| blank-aspect components in **the same exam** | refused |

So the only thing the condition would change is whether one exam may hold several
aspect-less components — and the domain says it may not: theory is one component, the
practical is four, one per aspect. The plain constraint therefore states something true,
and adding `condition=` would *loosen* it to permit a row that does not exist.

The general tell, worth carrying to the rest of this plan: **if you cannot name a row the
constraint would wrongly reject, the condition is buying nothing.** Contrast
`uq_one_correct_option_per_question`, where partiality is essential because a question has
many incorrect options and exactly one correct — there the excluded value genuinely repeats.

`Meta.ordering = ["position"]`.

- [ ] **Step 2: Migrate and read the DDL**

All three constraints appear inline in `CREATE TABLE` as named `CONSTRAINT` clauses — two
`UNIQUE`, one `CHECK` — because none of them is partial. Confirm the `CHECK` reads
`"marking_scheme" IN ('CHOICE', 'NUMERIC')`, and note the `FOREIGN KEY` arrives as a
separate `ALTER TABLE` marked `DEFERRABLE INITIALLY DEFERRED`, which is Django's default and
the reason deferred constraints are invisible to `pytest-django` — see the decisions log.

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_a_theory_exam_has_one_component` | one component, `marking_scheme=CHOICE`, blank aspect |
| `test_a_practical_exam_has_four_components_one_per_aspect` | DA/DB/AV/EX all save against one exam |
| `test_a_second_component_for_the_same_aspect_is_refused` | `IntegrityError`, `match="uq_one_component_per_aspect_per_exam"` |
| `test_a_second_component_in_the_same_position_is_refused` | `IntegrityError`, `match="uq_one_component_position_per_exam"` |
| `test_marking_scheme_is_not_silently_choice` | `IntegrityError`, `match="ck_component_marking_scheme_is_valid"`, on a component created with **no** `marking_scheme` |
| `test_deleting_an_exam_deletes_its_components` | `CASCADE`, asserted by reload |
| `test_components_are_ordered_by_position` | bare queryset, creation order disagreeing with expected order |

**Match on the constraint name in every `raises`.** This model has three constraints on one
table, so a bare `pytest.raises(IntegrityError)` can pass because the wrong one fired —
the same reason Task 2 needed it, one degree worse.

`test_marking_scheme_is_not_silently_choice` must **omit** `marking_scheme` rather than pass
an invalid string. Task 2 established why: the bug is Django supplying `''` for a value you
never gave, and a garbage string never exercises that path. Note `varchar(7)` is exact, so an
over-long invalid value would be rejected on column width before the `CHECK` ever runs.

- [ ] **Step 4: Run red, implement, green**

- [ ] **Step 5: Sweep, lint, commit**

New mutants: `ordering-component`, `uq-component-aspect` (drop `aspect` from the key),
`uq-component-position` (drop `position` from the key), `ondelete-component-exam`
(`CASCADE` → `PROTECT`), `ck-component-marking-scheme`. The first and fourth are model
mutants; the three constraint ones must be applied to the **migration** and will run
under `--create-db` — see the fresh-database rule in `CLAUDE.md`.

Subject: `feat(exams): add ExamComponent, one per marked section`

**Review gate.** Claude mutates each constraint off the migration and the `on_delete` off
the model, and reports which tests object.

---

## Task 4: Marking tables and grade bands as rows

**Files:**
- Modify: `exams/models/definition.py`
- Create: `exams/tables.py`
- Test: `tests/exams/test_tables.py`

**Interfaces:**
- Consumes: `ExamComponent` from Task 3; `scoring.MarkingTable`, `scoring.BandRow`,
  `scoring.GradeBand`.
- Produces: `build_marking_table(component) -> MarkingTable`,
  `build_grade_bands(component) -> list[GradeBand]`.

**The constraint this task exists to honour.** *Marking tables and grade bands are data,
never literals in Python.* FIG republishes them every cycle and does not finalise them until
after the first exam is sat. `scoring/` already takes them as arguments — `grade(percentage,
bands)` and `mark_numeric(response, expert_score, table)` — so this task is the adapter that
turns rows into those frozen dataclasses and nothing more.

**The two band sets differ and that is the point.** Excellent is **80%** for Difficulty and
**90%** for Artistry/Execution. `grade` already supports it because bands are an argument;
this task is what lets an official express it without a deploy.

- [ ] **Step 1: Write the row models**

**First, add `"django.contrib.postgres"` to `INSTALLED_APPS`** (found 2026-08-27). Without
it `ArrayField` fails a system check outright — `postgres.E005: 'django.contrib.postgres'
must be in INSTALLED_APPS in order to use ArrayField` — so `makemigrations` refuses before
anything else happens. It goes with the other `django.contrib.*` entries, above
`simple_history`. The column type is `numeric(m, n)[]` once it is there.

`MarkingTableRow(component, expert_minimum, percentages)` — `expert_minimum` a
`DecimalField`, `percentages` an `ArrayField` of `DecimalField` (Postgres-only, from
`django.contrib.postgres.fields`; this project is Postgres-only and says so).

`difference_steps` belongs to the **table**, not a row, so it is a field on `ExamComponent`:
an `ArrayField` of `DecimalField`. `MarkingTable.__post_init__` validates that every row's
`percentages` has the same length as `difference_steps`, so a mismatch raises at build time
rather than producing a silent wrong mark.

**Decided 2026-08-27: `blank=True, default=list`, plus a `CheckConstraint` tying it to
`marking_scheme`.** A theory component is marked by `mark_choice` and has no marking table
at all, so requiring `difference_steps` there forces a value that means nothing. But leaving
it merely optional lets a `NUMERIC` component be saved with no steps, and that only fails
much later — when someone tries to mark a candidate. So the pairing is a schema fact:

```python
models.CheckConstraint(
    condition=(
        Q(marking_scheme=MarkingScheme.NUMERIC, difference_steps__len__gt=0)
        | Q(marking_scheme=MarkingScheme.CHOICE, difference_steps__len=0)
    ),
    name="ck_component_steps_match_marking_scheme",
)
```

Django renders `__len` as `coalesce(array_length(...), 0)`, verified. Note `default=list` is
not a marking table expressed as a Python literal — it is *empty*, which is the same
distinction `to_decimal` draws between a blank answer and an unreadable one.

**This is the first constraint in the plan that spans two fields**, and it is what finally
connects `marking_scheme` to something. Compare `kind` and `aspect`, which are still
unconnected across tables — a theory `Exam` with a `DA` component remains representable.

`GradeBandRow(component, name, minimum)` — `minimum` a `DecimalField`, inclusive.
`UniqueConstraint(("component", "name"))`.

Both get `Meta.ordering` on the numeric field, ascending — **but for different reasons, and
only one of them is load-bearing.**

`MarkingTableRow.Meta.ordering` is enforced downstream: `MarkingTable.__post_init__`
**raises** on rows not sorted by `expert_minimum` ascending (`scoring/types.py:39-42`),
because `lookup` walks them positionally via `floor_band_index` and would otherwise return
the wrong cell in silence. Say that in a comment.

`GradeBandRow.Meta.ordering` has no such consumer. `grade(*, percentage, bands)` collects
every qualifying band and takes the highest minimum, and its docstring says outright that
"ordering of the bands is irrelevant". **Kept anyway, decided 2026-08-27, for display** — an
official reading a band set in arbitrary order is worse than the test is trivial — so it
needs a test of its own: assert the bare queryset comes back ascending by `minimum`.
Without that test the `ordering-gradebandrow` mutant cannot die, and it would be a mutant
that reports a gap where none exists.

- [ ] **Step 2: Write `exams/tables.py`**

Two functions, both taking a component and returning `scoring/` dataclasses. They are the
only place the two worlds meet.

Constructs: `tuple(...)` around the querysets, because `MarkingTable` and `BandRow` are
frozen dataclasses holding tuples; `BandRow(expert_minimum=..., percentages=tuple(...))`
per row.

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_the_legacy_single_row_scheme_builds` | one row, columns at 0.05 intervals; the built table's `lookup` reproduces a known cell |
| `test_a_two_dimensional_table_builds` | two rows with different `expert_minimum`; `lookup` picks the right row — **and the rows are inserted descending**, see below |
| `test_a_row_with_the_wrong_number_of_percentages_raises` | `MarkingTable.__post_init__`'s length check |
| `test_difficulty_and_artistry_bands_differ` | two components, 80 vs 90 minimum for Excellent; `grade(percentage=Decimal("85"), bands=...)` differs between them |
| `test_grade_bands_are_ordered_by_minimum` | bare queryset ascending, creation order disagreeing — the only thing that can kill `ordering-gradebandrow` |

Two more belong in `tests/exams/test_definition.py`, since the constraint is on
`ExamComponent`: `test_a_choice_component_may_not_have_difference_steps` and
`test_a_numeric_component_must_have_difference_steps`, both matching on
`ck_component_steps_match_marking_scheme`. Adding `difference_steps` also breaks the seven
Task 3 tests that create components — theory ones now omit the field, practical ones supply
a real list.

That last test is the one worth writing carefully: it must build **both** band sets and show
the same percentage grading differently. A test that builds one set proves nothing about
bands being data.

**`test_rows_out_of_order_raise` was dropped, 2026-08-27.** It could not be written as
named: with `Meta.ordering` in place the queryset always comes back sorted, so
`build_marking_table` never sees unsorted rows and the `ValueError` never fires. The claim
belongs inside `test_a_two_dimensional_table_builds` instead — **insert the rows with
descending `expert_minimum`**, so the table only builds if the ordering sorts them.

That insert order is load-bearing and was found the hard way. Written ascending, the test
passed with `Meta.ordering` deleted, because Postgres returns insertion order for a small
unordered scan and insertion order already matched. Inserted descending, deleting the
ordering fails at `scoring/types.py:40` — "Rows must be sorted by expert_minimum in
ascending order". Say so in a comment next to the inserts, or someone will tidy them back
into order.

**The general rule, worth applying to every test in this plan:** make the test's inputs
disagree with the order or shape the mutation would produce. Two instances hit in this task
alone — creation order matching expected order, and a `lookup` on the middle column of three,
where reversing the percentages is a fixed point and the assertion cannot see it.

- [ ] **Step 4: Run red, implement, green**

- [ ] **Step 5: Sweep, lint, commit**

New mutants: `ordering-markingtablerow` (dropping it must break the sorted-rows check),
`ordering-gradebandrow` (killed only by the queryset test above — model mutants both, since
`Meta.ordering` produces no DDL), `ck-component-steps-match-scheme` and
`uq-row-expert-minimum` (migration mutants, `--create-db`).

Subject: `feat(exams): load marking tables and grade bands from rows`
Body: that FIG republishes both every cycle, and that `scoring/` takes them as arguments
precisely so no deploy is needed.

**Review gate.** Claude checks that `exams/tables.py` is the only module importing both
`scoring` and `django`, and mutates the two orderings.

---

## Task 5: Membership — F9

**Files:**
- Create: `exams/models/membership.py`
- Modify: `exams/models/__init__.py`
- Test: `tests/exams/test_membership.py`

**Interfaces:**
- Consumes: `ExamComponent`; `questions.models.Question`, `questions.models.PracticalItem`.
- Produces: `ComponentQuestion(component, question, position)`,
  `ComponentPracticalItem(component, practical_item, position)`.

**This task is F9, and the fix is that the bug becomes unexpressible.** Legacy filtered
theory questions with `exam_level == user.level` against a scalar column, so a level 2
candidate sat level 2's 25 additions and never the 50 level 1 questions underneath —
confirmed from an old database, where the two levels share **no** question text at all. The
percentage looked entirely normal because the divisor was the filtered count.

**Membership is explicit rows, not a query.** A level 2 theory component *contains* 75
rows: the same `Question` objects level 1's component references, plus its own additions.
Selection at sitting time is "the component's members", and there is no level comparison
anywhere to get the direction of wrong. Overlap between levels is the same question row
referenced twice, never a copy of it — so an answer-key correction reaches every level at
once, which is F1's family.

- [ ] **Step 1: Write the through models**

Two explicit models rather than a plain `ManyToManyField`, for one reason: **order matters**
and a bare M2M has none. `position` a `PositiveSmallIntegerField`.

Each gets `UniqueConstraint(("component", "position"))` and
`UniqueConstraint(("component", <the member>))` — the second forbids the same question
appearing twice in one component, which is a real authoring mistake and would double its
weight in the mean.

`on_delete=models.PROTECT` on the question / practical item: a question referenced by an
exam must not vanish under it. `on_delete=models.CASCADE` on the component.

Make the `(component, position)` uniques `deferrable=Deferrable.DEFERRED` **only if** you
intend to write a reorder that renumbers inside one transaction. Task 7 of the questions
plan proved deferral is necessary but not sufficient for an admin reorder — `ModelForm._post_clean()`
runs `validate_unique()` before any `UPDATE` — so if no such code exists, leave them
immediate and say why in the commit.

- [ ] **Step 2: Migrate and read the DDL**

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_a_level_two_component_contains_level_ones_questions_too` | build a level 1 component with 3 questions and a level 2 component referencing **the same three rows** plus 2 more; assert level 2 has 5 members and that 3 of them are the *same objects* by pk |
| `test_correcting_a_question_reaches_every_component_referencing_it` | edit the question once, reload through both components, assert both see the change |
| `test_the_same_question_twice_in_one_component_is_refused` | `IntegrityError` on the member unique |
| `test_a_question_referenced_by_a_component_cannot_be_deleted` | `PROTECT` raises `ProtectedError` |
| `test_members_come_back_in_position_order` | bare queryset |

The first two are the F9 markers and they are the reason this task exists. The second is the
one that would have caught the legacy data shape: with duplicated rows per level, editing one
copy leaves the other cohort marked against a different key with no error anywhere.

- [ ] **Step 4: Run red, implement, green**

- [ ] **Step 5: Sweep, lint, commit**

New mutants: `ondelete-membership-question` (`PROTECT` → `CASCADE`),
`uq-membership-duplicate`, `ordering-membership`.

Subject: `feat(exams): make question membership explicit rows (F9)`
Body: that selection is membership, not a level comparison, so the equality-versus-lower-bound
bug has no expression; and that overlap is the same row referenced twice, so a key correction
cannot reach one cohort and miss another.

**Review gate.** Claude mutates `PROTECT` to `CASCADE` and confirms a test objects, and reads
the first test to check it asserts on **identity**, not on counts alone.

---

# Part B — sittings, the freeze, and results

## Task 6, Step 0: the custom user model — a prerequisite this plan did not have

**Decided 2026-08-30, before any of Task 6 was written.** `Sitting.judge` points at
`settings.AUTH_USER_MODEL`, which was unset and therefore `auth.User`. The spec's layout
lists `accounts/  # User, JudgeProfile, …`, so a custom user was always intended — and
this plan's claim that "the foreign key never has to move" is only true if that user model
exists *before* the foreign keys are written.

So: create `accounts/` with nothing but `class User(AbstractUser): pass`, add it to
`INSTALLED_APPS`, and set `AUTH_USER_MODEL = "accounts.User"`. The roster, `JudgeProfile`,
allauth and permissions stay in the accounts plan; this is only the model swap.

**Why now rather than later.** `simple_history` already added five `history_user` foreign
keys to `AUTH_USER_MODEL` in `questions/migrations/0005_add_history.py`, committed and
applied. Task 6 adds two more (`judge`, `certified_by`), Task 7 and 9 more again. Django's
documented position is that changing `AUTH_USER_MODEL` after tables exist requires manually
fixing the schema and moving data, and the dev database currently holds **two** user rows.
The cost only rises from here.

Note the migrations themselves are written against the *setting* — Django emits
`swappable_dependency(settings.AUTH_USER_MODEL)` — so it is the applied schema, not the
migration files, that pins the old model.

---

## Task 6: `Sitting` — enrolment is a pending sitting

**Files:**
- Create: `exams/models/sitting.py`
- Modify: `exams/models/__init__.py`
- Test: `tests/exams/test_sitting.py`

**Interfaces:**
- Consumes: `Exam`; `settings.AUTH_USER_MODEL`.
- Produces: `Sitting(judge, exam, status, started_at, submitted_at, certified_at,
  certified_by, outcome)`; `Status.PENDING|IN_PROGRESS|SUBMITTED|CERTIFIED`.

**A pending sitting *is* the enrolment; there is no separate model.** Enrolment is per exam,
and since theory and practical are separate exams, a candidate enrols for each independently
— sitting theory is not a prerequisite for sitting the practical.

- [ ] **Step 1: Write the model**

`judge` a `ForeignKey` to `settings.AUTH_USER_MODEL` with `on_delete=models.PROTECT` — a
sitting is a record of a real examination and must outlive account tidying.
`related_name="sittings"`.

`exam` a `ForeignKey`, `PROTECT`, `related_name="sittings"`.

`status` a `CharField` with `choices`, `default=Status.PENDING` — the one place in this
project a default is right, because a sitting that exists but has not started *is* pending
and there is no other meaningful initial value.

`started_at`, `submitted_at`, `certified_at` all `DateTimeField(null=True, blank=True)`.
`certified_by` a nullable `ForeignKey` to `AUTH_USER_MODEL` with a distinct `related_name`
(`certifications_made`) — two FKs to the same model need distinct accessors or Django's
system check fails.

`outcome` a `CharField(blank=True)`.

Add `HistoricalRecords()`. This is dispute material: who certified a sitting and when is
exactly the question history exists to answer.

- [ ] **Step 2: Decide the uniqueness, and write down why**

**No uniqueness on `(judge, exam)`. Settled 2026-08-25: a judge who fails may retake at a
later date.** So multiple sittings against the *same* `Exam` row are the ordinary case, not
an anomaly, and a `UNIQUE (judge, exam)` would forbid exactly the thing the federation
permits. This is the second time the same schema mistake has been avoided: F11 is the wound
left by `UNIQUE (sagf_id)` deciding a policy question the schema had no business deciding,
and the cost was that recertification could not be recorded at all.

**Two different repeats, one mechanism.** A *retake* is another sitting against the same
exam after a failure; a *recertification* is a sitting against a later year's exam. Both are
just another row in `sittings`, which is the point — the schema does not need to tell them
apart, and a report that does can ask the exam's year.

**The consequence for Task 9 and beyond: "the judge's result" is ambiguous.** Once retakes
exist, a judge can hold two `ComponentResult` sets for one exam. Nothing in this plan picks
between them, and nothing should — which sitting counts is a federation rule (latest?
best? latest passing?) and belongs with the certification logic in the accounts plan. Write
a test that a judge can hold two sittings against one exam and that **both survive**, and
leave the selection alone.

- [ ] **Step 3: Migrate and read the DDL**

- [ ] **Step 4: Write the failing tests**

| test | asserts |
|---|---|
| `test_a_judge_accumulates_sittings_across_years` | two sittings, 2026 and 2030, both survive; assert `judge.sittings.count() == 2` **after reload** |
| `test_a_judge_can_retake_the_same_exam_after_failing` | two sittings against **one** `Exam` row, both survive — the retake marker, and what a `UNIQUE (judge, exam)` would break |
| `test_a_new_sitting_is_pending` | the default |
| `test_a_judge_with_no_practical_sitting_has_no_practical_result` | the **F10 marker** — enrol in theory only, assert `Sitting.objects.filter(judge=..., exam__kind=PRACTICAL).exists() is False`, and that nothing anywhere fabricates a zero |
| `test_a_judge_with_sittings_cannot_be_deleted` | `PROTECT` |
| `test_certifying_records_who_and_when` | set `certified_by` and `certified_at`, reload, assert both; then assert `sitting.history.count() == 2` and that `history.last()` has neither |

The F10 test is an **absence** test, so it needs a positive control in the same test or it
passes against an empty database: assert the theory sitting *does* exist first.

- [ ] **Step 5: Run red, implement, green**

- [ ] **Step 6: Sweep, lint, commit**

New mutants: `history-off-sitting`, `ondelete-sitting-judge`, `status-default-pending`.

Subject: `feat(exams): add Sitting, where a pending sitting is the enrolment (F10, F11)`

**Review gate.** Claude checks the F10 test has a positive control, and mutates the history
off `Sitting`.

---

## Task 7: `SittingItem` and the freeze

**Files:**
- Modify: `exams/models/sitting.py`
- Create: `exams/freeze.py`
- Test: `tests/exams/test_freeze.py`

**Interfaces:**
- Consumes: `Sitting`, `ExamComponent`, the membership models.
- Produces: `SittingItem(sitting, component_name, component_position, marking_scheme,
  position, question_snapshot, marking_key, response, percentage)`;
  `start_sitting(sitting) -> None`.

**This task is F1.** Legacy recomputed a result from the live question bank every time it
was displayed, so correcting an answer key silently rewrote history. Here the sitting copies
what it presented, and displaying a result never touches `questions/`.

**Freeze at start, not at submission.** `theory_exam()` re-queried the bank on every GET, so
a reload could serve a different set — which is why the `theory_loaded` cookie existed to
forbid reloading. With freeze-at-start, a reload is safe: same sitting, resumed.

**JSONB appears here and nowhere else.** Live content is relational because it is *edited*;
frozen content is JSON because it is *recorded* — written once, never queried into, read back
whole. Storage follows lifecycle, not data shape.

**It also closes F2 structurally.** Legacy named each radio from `question.id` and built the
answer key from `question_id` — different columns that coincided only because both were
populated sequentially. Diverge them and every lookup misses, every candidate scores zero,
silently, and the score cannot distinguish "answered wrongly" from "was never asked". Here
the marking key is a **field on the item it marks**. There is no lookup across two
structures, so there is no pair of keys that can drift apart.

- [ ] **Step 1: Write `SittingItem`**

`sitting` FK, `CASCADE`, `related_name="items"`.

**Component identity is copied, not referenced.** `component_name` a `CharField`,
`component_position` a `PositiveSmallIntegerField`, `marking_scheme` a `CharField`. A
`ForeignKey` to `ExamComponent` would leave the grouping — and therefore the component
percentages — hostage to a later edit of the live component, which is F1 wearing a different
hat. Grouping items for `score_component` must use the frozen name.

`question_snapshot`, `marking_key` and `response` are `JSONField`. `response` gets
`null=True` and **no default** — absence is not a value, and `{}` would be a response.

`percentage` a `DecimalField(max_digits=5, decimal_places=2, null=True)` — null until
submission, **not zero**. Null is the F10/F3 distinction: unmarked is not the same as
scored nothing.

**It is called `percentage`, not `marks_awarded`, and there is no `max_marks`** (revised
2026-09-03). `mark_choice` returns `Decimal("100")` or `Decimal("0")` and `mark_numeric`
returns a `table.lookup`, so what lands here is already a percentage — `score_component`
even names its parameter `item_percentages`. Calling it marks is **F5's exact slip**:
legacy summed twenty marks worth five each and printed the total with a `%` on it, with
nothing in the code recording that the two were different quantities. `max_marks` was
dropped because nothing in Tasks 8 or 9 reads it, and nothing can: at `100` it is a
constant column, and at `5` it is the marks-based model this rebuild abandoned.

`max_digits=5` is load-bearing — a percentage reaches `100.00`, which is five digits, and
Postgres **errors** rather than rounds on precision overflow. `max_digits=4` would fit
`99.99` and reject a full score.

`Meta.constraints`: `UniqueConstraint(("sitting", "position"))`.
`Meta.ordering = ["position"]`.

- [ ] **Step 2: Write `start_sitting`**

Takes a pending sitting. Walks the exam's components in `position` order, and each
component's members in `position` order, writing one `SittingItem` per member with a running
overall `position`. Sets `status` to `IN_PROGRESS` and `started_at` to `timezone.now()`.

Constructs: `transaction.atomic` around the whole thing; `select_related` /
`prefetch_related` on the membership queryset so a 75-question theory exam is not 75 queries;
`django.utils.timezone.now`, never `datetime.now`.

Guard: calling it on a sitting that is not `PENDING` must raise rather than re-freeze. A
second freeze would discard responses.

**What goes in `question_snapshot`.** Everything a candidate sees, rendered flat: the
question's reference and its blocks' kind/text/image/video, and for choice questions each
option's blocks. Not the model instances — plain dicts of strings.

**What goes in `marking_key`.** For `CHOICE`, the correct option's identifier. For
`NUMERIC`, the expert score as a **string**, because JSON has no `Decimal` and float would
reintroduce F3. `to_decimal` reads it back.

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_starting_a_sitting_creates_one_item_per_member` | counts match, positions are 1..n with no gaps |
| `test_the_snapshot_survives_editing_the_question` | **the F1 marker** — freeze, then change the question's text and its correct option, reload the item, assert the snapshot and the marking key are unchanged |
| `test_the_marking_key_holds_the_expert_score_as_a_string` | `isinstance(item.marking_key["expert_score"], str)` after **reload**, not on the object `create()` returned |
| `test_starting_an_already_started_sitting_raises` | the guard |
| `test_a_frozen_response_starts_null_not_empty` | `item.response is None`, and that `None` and `{}` are distinguishable |
| `test_items_come_back_in_position_order` | bare queryset |

The second test is the whole point of the app. Write it first.

- [ ] **Step 4: Run red, implement, green**

- [ ] **Step 5: Count the queries**

Wrap `start_sitting` in `django_assert_num_queries` with a 75-member component. Task 7 of
the questions plan found a 20-row changelist costing 25 queries because `__str__` crossed a
relation; a freeze that costs one query per member will be worse and nobody will see it until
a real exam starts.

- [ ] **Step 6: Sweep, lint, commit**

New mutants: `freeze-reuses-live-question` (replace the snapshot copy with a FK lookup — the
F1 test must die), `ordering-sittingitem`, `freeze-guard` (`if sitting.status != PENDING` →
`if False`).

Subject: `feat(exams): freeze sitting items at start (F1, F2)`
Body: why freeze-at-start rather than at submission, and that the component identity is
copied rather than referenced so a later edit cannot regroup a finished result.

**Review gate.** Claude mutates the freeze into a live lookup and confirms the F1 test dies.

---

## Task 8: Responses and submission

**Files:**
- Create: `exams/marking.py`
- Test: `tests/exams/test_marking.py`

`exams/models/sitting.py` was listed here and is not needed (removed 2026-09-07):
`percentage` was defined on `SittingItem` in Task 7 and `Status.SUBMITTED` already
exists, so nothing in this task changes a model.

**Interfaces:**
- Consumes: `SittingItem`, `exams.tables`, `scoring.mark_choice`, `scoring.mark_numeric`.
- Produces: `record_response(item, response) -> None`, `submit_sitting(sitting) -> None`.

**Marks are stored, not recomputed.** `submit_sitting` writes `percentage` onto every
item once. Nothing later recalculates it.

**Two things this task must decide, neither of which the plan settled** (noted
2026-09-07, before any code was written).

**The shape of `response`.** It is a `JSONField` and nothing says what goes in it.
Either a bare JSON string, so `item.response == "2"` and `mark_choice` takes it
directly, or a one-key dict, `{"answer": "2"}`, matching `marking_key`'s shape and
leaving somewhere for the timer data the domain notes promise. Recommendation is the
dict, on the weak grounds that two JSON columns side by side in one row with different
shapes get misread. `None` versus `{}` stays meaningful either way.

**How a numeric item finds its marking table — decided 2026-09-08: freeze the table
into the item.** `SittingItem` deliberately holds no foreign key to `ExamComponent`,
that absence being Task 7's whole point, so `build_marking_table(component)` has
nothing to be called with at submission. Looking the component up by the frozen
`component_name` is **F2's shape**, and worse than it looks: there is no unique
constraint on `(exam, name)` — only on `(exam, position)` and `(exam, aspect)` — so
the name is not a key at all.

`marking_key` therefore carries the table alongside the expert score, every number a
string for the reason the expert score already is one:

```json
{
  "expert_score": "8.50",
  "marking_table": {
    "difference_steps": ["0.10", "0.20", "0.50"],
    "rows": [
      {"expert_minimum": "0.00", "percentages": ["100.00", "90.00", "50.00"]}
    ]
  }
}
```

**What this buys is that `submit_sitting` becomes a pure function of the row it is
marking** — no lookup, no key, no second table, and no window between freezing and
submitting in which an edit could change a candidate's mark. Task 8's own
`test_marks_are_not_recomputed_after_submission` only closes the window *after*
submission; this closes the one before it.

**What it costs is duplication, and it was measured rather than guessed.** A
generously sized table (20 expert bands × 10 difference steps) serialises to 2.5 KB —
three and a half times a four-option `question_snapshot` at 718 bytes. A practical
sitting has 20 numeric items sharing 4 distinct tables, so 51 KB is stored where 10 KB
would do: **41 KB of waste per sitting**, or about 2 MB per fifty sittings. At the
scale in Open Questions ("candidates per sitting: assumed tens") that is not a
consideration. Rejected alternatives were a lookup by `component_position`, which
keeps a live read in the marking path, and freezing the four tables once onto the
`Sitting`, which saves 41 KB per sitting at the price of a migration and a key.

**Consequence for Task 7's code:** `exams/freeze.py` changes. `_frozen_practical_item`
needs the component's table, so `start_sitting` builds it once per component — not per
item — and passes it in. `exams/tables.py` gains the serialise/deserialise pair beside
`build_marking_table`: one turning a `MarkingTable` into that dict for the freeze, one
turning it back for marking. Neither touches the database, so the module keeps its
property of being the only place `scoring` and Django meet.

- [ ] **Step 1: Write the failing tests** — the table below, one at a time

Written before the code, not after. The step order here said otherwise until 2026-09-07
and Task 7 ignored it in practice; see `CLAUDE.md`, "He writes the test before the code
where the plan says write the failing tests". Start with
`test_a_correct_choice_scores_full_marks`: it needs no marking table, so it drives
`record_response` and the `CHOICE` branch into existence without waiting on the
decision above.

- [ ] **Step 2: Write `record_response`**

Writes `response` onto one item and nothing else. Refuses when the sitting is not
`IN_PROGRESS` — a submitted sitting is closed, and the timer that moves a candidate on is a
runner concern, not a model one.

- [ ] **Step 3: Write `submit_sitting`**

For each item: `mark_choice(response, key)` when `marking_scheme` is `CHOICE`,
`mark_numeric(response, expert_score, table)` when `NUMERIC`. Store the result in
`percentage`. Set `status=SUBMITTED`, `submitted_at=timezone.now()`.

`to_decimal` turns the stored string key into a `Decimal`. **Never `float(...)`** — F3.

**F4 does not close itself.** `to_decimal` *raises* `UnparseableAnswer` on `"abc"`; it
returns `None` only for blank. `mark_numeric` calls it with no `try`, so the exception
propagates out — which is precisely the legacy crash F4 names. `submit_sitting` is what
has to catch it and store `0`. Corrected 2026-09-07: this step previously read as though
`mark_numeric` handled it.

An unanswered item marks as **0**, and that is correct: the candidate sat the component and
did not answer. It is categorically different from F10's absent component, which has no
sitting and therefore no items at all. Write that distinction into a comment, because the
next reader will conflate them — legacy did.

The tests, for reference from Step 1:

| test | asserts |
|---|---|
| `test_a_correct_response_scores_full_marks` | 100. On its own it cannot tell marking from `percentage = 100`; the unanswered test below is what gives it meaning |
| `test_an_unanswered_item_scores_zero_but_is_not_absent` | `percentage == 0` **and** the item exists — the F10/F3 distinction |
| `test_a_numeric_response_is_marked_through_the_marking_table` | a known cell, asserted as `Decimal`, after reload |
| `test_an_unreadable_numeric_response_scores_zero` | `"abc"` → 0, not a crash — **F4** |
| `test_marks_are_not_recomputed_after_submission` | **the F1 test with teeth** — submit, then change the marking table rows *and* the question, reload, assert `percentage` is unchanged |
| `test_submitting_twice_raises_an_exception` | the submit guard |
| `test_a_submitted_sitting_refuses_further_responses` | **added 2026-09-12.** `record_response` after submission raises. Must reuse the *same* item object — a freshly read one already refuses, and the bug this pins was a cached FK |
| `test_the_mark_uses_the_table_frozen_at_start_of_sitting` | **added 2026-09-12, and the only test with teeth for the freeze-the-table decision.** Edit the marking table *between* the freeze and the submission, then assert the frozen numbers were used. Needs a positive control on the edit: with its filter matching no rows, `marking-uses-live-table` survives again |

- [ ] **Step 4: Green, with every test having been seen red first**

- [ ] **Step 5: Sweep, lint, commit**

New mutants, all six killed: `marking-float-cast`, `marking-no-unparseable-catch`,
`marking-uses-live-table`, `record-guard-reads-cached-fk`, `submit-guard-removed`,
`marking-scheme-branch-swapped`. **Add `tests/exams/test_marking.py` to `EXAMS_TESTS`
first** — `TEST_PATHS` is built from it, so without that every marking mutant reports
SURVIVED.

Subject: `feat(exams): mark a sitting at submission and store the marks (F1, F3, F4)`

**Review gate.** Claude mutates `to_decimal` to `float` and confirms a test objects.

Recorded 2026-09-12: it does, but on a `TypeError` rather than a failed assertion.
`Decimal` refuses `float` operands outright, so F3 cannot be *quiet* here — a float
reaching a mark is a crash, not a wrong number. Note the near-miss: mutating
`Decimal(x)` into `Decimal(str(float(x)))` **survives**, because `8.50` round-trips
through binary floating point exactly and every operation afterwards stays `Decimal`.
The mutation has to put a float into the subtraction, not merely pass a value through
one.

---

## Task 9: Component results — F5

**Files:**
- Modify: `exams/models/sitting.py`, `exams/marking.py`
- Test: `tests/exams/test_results.py`

**Interfaces:**
- Consumes: `SittingItem`, `scoring.score_component`, `scoring.grade`, `exams.tables`.
- Produces: `ComponentResult(sitting, component_name, percentage, grade_name)`.

**This is F5.** Legacy summed 20 marks worth 5 each and called the total a percentage, which
was only ever correct because 5 apparatus × 4 aspects = exactly 20. Nothing recorded the
dependency; a sixth apparatus would have scored everyone out of 125 while still printing "%".
`score_component` takes the **mean of per-item percentages** and there is no magic number.

**The grade is stored too.** Grade bands are rows an official can edit. If the grade were
computed at display time, editing a band would silently regrade every historical result —
F1 again, one level up. Store `percentage` and `grade_name` at submission.

**The bands must be frozen as well, and this task cannot start without deciding it**
(noted 2026-09-13). `build_grade_bands(component)` needs an `ExamComponent`, and
`SittingItem` deliberately holds no foreign key to one — the same wall Task 8 hit with
the marking table, and there is no minimal path around it. Freeze them the same way:
a `grade_bands` `JSONField` on `SittingItem`, written for every item at start, read
back from any item of a group at submission. Measured before choosing: five bands
serialise to **180 bytes**, a fourteenth of the marking table's 2.5 KB, so 3.6 KB per
practical sitting — the duplication argument that made a `Sitting`-level store worth
considering for the table does not apply here. One mechanism, and `submit_sitting`
keeps reading only the rows it is marking.

**The freeze refuses a component with no grade bands** (decided 2026-09-15). `grade`
raises on an empty band list, so without a guard the failure arrives at *submission* —
after a candidate has sat the whole paper. The marking table already failed at freeze,
but only because `MarkingTable.__post_init__` happens to validate and `GradeBand` does
not; that was an accident of where a check lived, not a decision. `start_sitting` now
raises `ComponentHasNoGradeBands(component.name)`. Cost accepted knowingly: every
component built in `test_freeze.py` must now author bands it never reads, through a
`_with_grade_bands` helper. **The guard shipped broken first** — renamed at the class
but not at the `raise`, so firing it gave `NameError` — under a fully green suite,
because fixtures that make every other test work are exactly what stop a guard ever
firing. Its own test is what exposed it.

- [ ] **Step 1: Write the failing tests** — the table below, one at a time

Before the code, not after; the step order said otherwise until 2026-09-13 and Tasks 7
and 8 both inverted it in practice. Start with the F5 marker: it fails on
`ComponentResult` not existing, which is the red you want.

- [ ] **Step 2: Write `ComponentResult`**

`sitting` FK `CASCADE`, `related_name="results"`. `component_name` a `CharField` — the frozen
name from Task 7, which is what groups the items. `percentage` a
`DecimalField(max_digits=5, decimal_places=2)`. `grade_name` a `CharField`.

`UniqueConstraint(("sitting", "component_name"))`.

- [ ] **Step 3: Extend `submit_sitting`**

After marking every item, group them by `component_name`, call `score_component` on each
group's `percentage`, then `grade(percentage=..., bands=build_grade_bands(...))`, and
write one `ComponentResult` per group.

`score_component` **raises** on an empty sequence rather than returning 0 — let it. A
component with no items is a bug in the freeze, and a silent 0 is the F10 shape.

The tests, for reference from Step 1:

| test | asserts |
|---|---|
| `test_a_component_percentage_is_the_mean_not_the_total` | **the F5 marker** — five items at 100 give 100, not 500; and with a sixth item the answer is still ≤ 100 |
| `test_a_practical_sitting_produces_four_component_results` | one per aspect |
| `test_the_two_band_sets_grade_the_same_percentage_differently` | Excellent is **80%** for Difficulty and **90%** for Artistry/Execution, so `Decimal("85")` grades Excellent under a `DA` component and one band lower under an `AV` one. Build both components and assert the two `grade_name` values differ |
| `test_editing_a_grade_band_does_not_regrade_a_submitted_sitting` | store, edit the band row, reload, assert `grade_name` unchanged |
| ~~`test_a_component_with_no_items_raises_rather_than_scoring_zero`~~ | **Dropped 2026-09-13: unreachable.** `submit_sitting` groups items by `component_name`, so a component with no items produces no group and `score_component` is never called with an empty sequence. The guard is real and tested inside `scoring`'s own suite; there is no path to it from here |
| `test_starting_a_sitting_raises_on_a_component_with_no_grade_bands` | **added 2026-09-15, lives in `tests/exams/test_freeze.py`.** The guard's own test. Kills both the guard's deletion (`DID NOT RAISE`) and the half-finished rename it actually shipped with (`NameError`). Must not use `_with_grade_bands` — the absence is the experiment |

- [ ] **Step 4: Green, with every test having been seen red first**

- [ ] **Step 5: Sweep, lint, commit**

New mutants: `results-sum-not-mean` (`score_component` → `sum`), `results-regrade-on-read`.

Subject: `feat(exams): store component percentages and grades at submission (F5)`

**Review gate.** Claude mutates the mean into a sum and confirms the F5 test dies.

---

## Task 10: Admin, and the backfill

**Files:**
- Create: `exams/admin.py`
- Modify: `tools/mutation_sweep.py`
- Test: `tests/exams/test_admin.py`

**Interfaces:**
- Consumes: everything above.

**Two audiences and they need opposite things.** `Exam`, `ExamComponent`, the membership and
the table rows are **edited** — full admin, inlines, search. `Sitting`, `SittingItem` and
`ComponentResult` are **records** — visible, never editable. A `ModelAdmin` with
`has_change_permission` returning `False` is the construct; a read-only admin over frozen
rows is the difference between an audit trail and a suggestion.

- [ ] **Step 1: Register the definition models**

`ExamAdmin` with a `ComponentInline`. `ExamComponentAdmin` with `ComponentQuestionInline`,
`MarkingTableRowInline` and `GradeBandRowInline`.

Remember Task 7 of the questions plan: **the inline prefix is the FK's `related_name`**, not
`<model>_set`, and every inline on a page needs its four management-form keys or the formset
never binds. A `200` from an admin POST means the form re-rendered — it failed.

`list_select_related` wherever `list_display` crosses more than one relation.

- [ ] **Step 2: Register the sitting models read-only**

`SimpleHistoryAdmin` on `Sitting`. `has_add_permission` and `has_change_permission` returning
`False` on `SittingItem` and `ComponentResult`; `readonly_fields` naming every field.

- [ ] **Step 3: Write the failing tests**

| test | asserts |
|---|---|
| `test_the_exam_changelist_renders_an_exam` | create with `objects.create`, assert a **distinctive** reference appears — never page chrome |
| `test_a_sitting_item_cannot_be_changed_through_the_admin` | POST to the change URL, assert a redirect or 403 **and** that the row is unchanged after reload |
| `test_the_sitting_history_page_shows_the_previous_status` | assert on the **old** value; the current one is chrome, because `__str__` renders in the page title |
| `test_admin_pages_require_login` | parametrized over the changelist URL names, no `django_db` marker |

The second test's assertion must be on the **data**, not the status code. A read-only admin
that returns 302 and saves anyway is exactly the failure it exists to catch.

- [ ] **Step 4: Run red, implement, green**

- [ ] **Step 5: Full sweep and the plan close**

```bash
../.venv/bin/python tools/mutation_sweep.py
../.venv/bin/python -m pytest -q && ../.venv/bin/ruff format . && ../.venv/bin/ruff check .
```

Expect zero survivors bar any declared out of scope. Then update `CLAUDE.md`: the state
block, the next action (accounts and the roster), and F1/F5/F9/F10/F11/F12 marked closed with
the tests that pin them.

Subject: `feat(exams): author exams and read sittings in the admin`

**Review gate.** Claude runs the sweep and reports the survivor count.

---

## Open questions this plan raises

1. ~~May a judge sit the same exam twice?~~ **Resolved 2026-08-25: yes — a judge who fails
   may retake at a later date.** No constraint on `(judge, exam)`, now for a stated reason
   rather than an absent one. What it opens instead: **which sitting counts** when a judge
   holds two results for one exam — latest, best, or latest passing. That is a certification
   rule and belongs with the accounts plan, not here.
2. **What does a candidate see between `submitted` and `certified`?** The spec says scoring
   and certification are separate events. Whether the percentage is visible before an
   official signs it off is a policy question, not a modelling one.
3. **The overall category.** Four grades to one category, per §2.6. Needs Task 9's output and
   the accounts plan's certification history, since the examination result is an upper bound
   on the award, not the award.
4. **`difference_steps` on the component or on the table?** Task 4 puts it on
   `ExamComponent`. If a component ever needs two marking tables, it moves.
