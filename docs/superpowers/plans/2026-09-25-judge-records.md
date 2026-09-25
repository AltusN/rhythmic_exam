# Judge Records Implementation Plan

**Goal:** Record who may sit which exam, enrol them against that record, and turn a submitted
practical sitting into a certification an official signs — with the bounds the system can
derive stored beside the category the official chose.

**Architecture:** Identity lives in `accounts` (`JudgeProfile`, `RosterEntry`); everything
with a sitting in it lives in `exams` (enrolment, `Certification`, the award), so the
dependency runs `exams → accounts` only. Rules are pure functions over plain values —
`exams/eligibility.py`, `exams/awards.py` — and the services beside them load rows, call the
rules and write the results, the `tables.py` / `freeze.py` split again. Part A is the rules,
their tables and enrolment; Part B is certification, the two imports and the admin.

**Tech Stack:** Django 6.1, Postgres 17 (`ArrayField`), `pytest-django`,
`django-simple-history`, ruff. `scoring/` is consumed as a plain library.

**Spec:** `docs/superpowers/specs/2026-09-25-judge-records-design.md`. It amends the original
spec's Accounts and Eligibility sections and its award formula; read its **Corrections**
section first. The FIG source is the General Judges' Rules 2025–2028, chapter 2, cited there
by URL.

**Working agreement:** `CLAUDE.md` governs. Altus writes every line of implementation code
and every test. This plan names files, constructs and decisions; it does not contain finished
implementations. Claude writes the mutation catalogue entries (agreed 2026-09-06) and reviews
*and mutates* at every gate.

## Global constraints

- **`rhythmic/scoring/` imports nothing from Django.** The new pure modules in `exams/` —
  `eligibility.py`, `awards.py` — hold themselves to the same rule by discipline: no model
  import, no query. Their tests need no `django_db` marker, and a test that needs one is a
  sign the rule leaked.
- **`Decimal` everywhere for percentages. Never compare grades or categories as strings** —
  F3's shape. Grades compare by rank.
- **The §2.6 table, cycles and grade bands are data, never literals in Python.**
- **No real exam content and no real judge data in this repository.** Roster and category
  fixtures are synthetic: invented `sagf_id`s, `example.com` addresses.
- **No test is accepted until it has been shown red.** Claude mutates and reports at every
  gate. Guards especially: the Task 9 lesson from the exams plan is that a guard clause is
  the production code a suite is least likely to execute.
- **Run `../.venv/bin/python tools/mutation_sweep.py` at the end of every task.**
- **Commits:** scope `accounts` for Task 1 and the roster import, `exams` for the rest. Cite
  the FIG section where a rule comes from one: `feat(exams): refuse a second retest in a
  cycle (§2.7)`.

## What this plan deliberately leaves out

- **Sign-in.** Plan 2: allauth, Google, the verified-email match against `RosterEntry`, and
  attaching a `User` to a `JudgeProfile` created by the category import. Until then users
  come from the admin and `createsuperuser`, as now.
- **Judging experience.** Not modelled (decided 2026-09-25). The official applies it and the
  reason records it.
- **Candidate-facing results.** "No results before certification" is recorded for the React
  island. There is no candidate-facing view in this plan to break it.

---

## File structure

```
rhythmic/accounts/
  models.py            User (exists), JudgeProfile, RosterEntry
  roster.py            parse / diff / apply for the roster import
  admin.py
rhythmic/exams/
  models/
    definition.py      + Cycle, CategoryRequirement
    sitting.py         Sitting (+ candidate_number, override, − certification fields),
                       SittingItem (+ component_aspect), ComponentResult (+ aspect)
    certification.py   Certification                                   — recorded
  eligibility.py       refusals()                   pure
  awards.py            dimension grades, examination_category, award_bounds   pure
  enrolment.py         enrol()
  certification.py     certify()
  category_import.py   parse / diff / apply for imported certifications
  admin.py
rhythmic/tests/accounts/
  __init__.py          required — see Layout in CLAUDE.md
  test_models.py  test_roster.py
rhythmic/tests/exams/
  test_cycles.py  test_eligibility.py  test_enrolment.py  test_awards.py
  test_certification.py  test_category_import.py  (+ test_admin.py, test_freeze.py extended)
```

**`certification.py` twice, deliberately.** `models/certification.py` is the record;
`exams/certification.py` is the service that writes it — the same pairing as
`models/sitting.py` and `freeze.py`. If the name collision reads badly by Task 9, rename the
service `certify.py` and say so.

---

# Part A — the rules, their tables, and enrolment

## Task 1: `JudgeProfile` and `RosterEntry`

**Files:**
- Modify: `accounts/models.py`, `accounts/admin.py`
- Create: `accounts/migrations/0002_…` (generated), `tests/accounts/__init__.py`,
  `tests/accounts/test_models.py`
- Modify: `tools/mutation_sweep.py` — **Claude's**: an `ACCOUNTS_TESTS` list, an `"accounts"`
  entry in `SCOPES`, and `ACCOUNTS_TESTS` in `TEST_PATHS`

**Interfaces:**
- Produces: `JudgeProfile(user: OneToOne[User] | None, sagf_id: str)`, reverse accessor
  **`user.judge_profile`**; `RosterEntry(sagf_id, email, year, levels: list[int])`.

- [ ] **Step 1: Write the failing tests** — the table below, one at a time, each red first

- [ ] **Step 2: `JudgeProfile`**

`user` is a `OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
on_delete=models.PROTECT, related_name="judge_profile")`. **Nullable** because the category
import creates judges before they have a login; `OneToOneField` is already unique, and
Postgres treats `NULL`s as distinct, so many unlinked profiles coexist. `PROTECT` because
deleting a login must not delete a judge's history. `sagf_id` a `CharField`, unique.

`HistoricalRecords()` — binding a login to a judge is exactly what a dispute asks about.

- [ ] **Step 3: `RosterEntry`**

`sagf_id` a `CharField`, **not** a foreign key: the roster predates the account and is
matched by value. `email` an `EmailField`. `year` a `PositiveSmallIntegerField`. `levels`
an `ArrayField(models.PositiveSmallIntegerField())` from `django.contrib.postgres.fields` —
`django.contrib.postgres` is already in `INSTALLED_APPS`. `UniqueConstraint` on
`("sagf_id", "year")`. `HistoricalRecords()`.

**Lowercase the email in `save()`**, not in the import alone — Plan 2 matches against it, and
an admin edit must not store `Judge@Example.com` that the match then misses.

- [ ] **Step 4: Register both in the admin**, plain `ModelAdmin` / `SimpleHistoryAdmin`

| test | asserts |
|---|---|
| `test_a_judge_profile_needs_no_user` | create with `user=None`, re-read with `objects.get`, assert `user_id is None` |
| `test_two_profiles_without_users_coexist` | two `user=None` profiles both save — pins that nobody "fixed" the nullable 1:1 into a unique non-null column |
| `test_a_user_has_at_most_one_profile` | a second profile for the same user raises `IntegrityError` — use `pytest.raises` inside `transaction.atomic()` |
| `test_a_judge_appears_once_per_roster_year` | same `(sagf_id, year)` twice raises; same `sagf_id` in two years saves |
| `test_a_roster_email_is_stored_lowercase` | save `Judge@Example.COM`, **re-read from the database**, assert lowercase — the instance-versus-row disguise, since `save()` could lowercase the instance and store the original |
| `test_roster_levels_round_trip` | `levels=[1, 3]` re-read equals `[1, 3]` — order preserved |

Subject: `feat(accounts): add judge profiles and the yearly roster`

**Review gate.** Claude adds catalogue entries (`uq-roster-sagf-year` in the migration,
`roster-email-not-lowered`, `judge-profile-user-not-null` in the migration) and runs the
sweep with the new scope.

---

## Task 2: `Cycle` and `CategoryRequirement`

**Files:**
- Modify: `exams/models/definition.py`, `exams/models/__init__.py`, `exams/admin.py`
- Create: generated migration, `tests/exams/test_cycles.py`

**Interfaces:**
- Produces: `Cycle(name, first_year, last_year)`, `Cycle.objects.for_year(year) -> Cycle`
  (raises `Cycle.DoesNotExist`); `CategoryRequirement(cycle, category: int 1–4, dimension:
  Dimension, minimum_grade: str)`; `Dimension.DIFFICULTY | EXECUTION | ARTISTRY`
  (`TextChoices`).

- [ ] **Step 1: Write the failing tests** — the table below

- [ ] **Step 2: `Cycle`**

`CheckConstraint(condition=Q(first_year__lte=F("last_year")))`. Cycles must not overlap, or
`for_year` has two answers; the construct for that in Postgres is an
`ExclusionConstraint` over an integer range, which needs `btree_gist`. **Simpler and
sufficient:** unique `first_year`, unique `last_year`, and let `for_year`'s `.get()` raise
`MultipleObjectsReturned` if an official ever builds an overlap — `get()` fails loudly, which
is why it carries its own control. Record that choice in a comment.

`for_year` is a custom manager method:
`self.get(first_year__lte=year, last_year__gte=year)`.

- [ ] **Step 3: `CategoryRequirement`**

`category` a `PositiveSmallIntegerField` with `CheckConstraint` 1–4. `UniqueConstraint` on
`(cycle, category, dimension)` — two minimums for one cell is F2's two-answer-keys shape.
Inline under `Cycle` in the admin, like grade bands under a component.

| test | asserts |
|---|---|
| `test_a_year_finds_its_cycle` | cycles 2025–2028 and 2029–2032; `for_year(2028)` and `for_year(2029)` each return the right one — **the two edges, one either side**, so `lt`/`gt` mutants die |
| `test_a_year_outside_every_cycle_raises` | `for_year(2040)` raises `Cycle.DoesNotExist` |
| `test_a_cycle_cannot_end_before_it_starts` | `first_year=2029, last_year=2025` raises `IntegrityError` |
| `test_a_category_has_one_minimum_per_dimension` | a duplicate `(cycle, 1, DIFFICULTY)` raises |
| `test_category_five_is_refused` | `category=5` raises — the check constraint |

Subject: `feat(exams): add cycles and the category table as rows`

**Review gate.** Migration mutants for the check and unique constraints; `for-year-lt` and
`for-year-gt` on the manager.

---

## Task 3: The eligibility rule — pure

**Files:**
- Create: `exams/eligibility.py`, `tests/exams/test_eligibility.py`

**Interfaces:**
- Produces: `Refusal` (an `enum.Enum`: `NOT_ON_ROSTER`, `LEVEL_NOT_PERMITTED`, `RETEST_USED`,
  `ALREADY_ENROLLED`) and

  ```python
  def refusals(*, roster_levels: Sequence[int] | None, exam_level: int,
               prior_practical_sittings: int, has_open_sitting: bool,
               exam_is_practical: bool) -> list[Refusal]
  ```

  `roster_levels=None` means *no roster entry*; `[]` means *an entry permitting nothing*.
  Those are different refusals, and that is the F3/F10 distinction again — absence is not an
  empty value.

**No Django import in this file.** Its tests have no `django_db` marker. Use `enum.Enum`, not
`models.TextChoices` — the latter would import Django.

- [ ] **Step 1: Write the failing tests**, `parametrize` with `ids`, one row per rule

- [ ] **Step 2: Write `refusals`**

Collect every applicable refusal, **not the first** — an official deciding whether to
override needs the whole list. `RETEST_USED` when `exam_is_practical and
prior_practical_sittings >= 2`.

| id | inputs | expected |
|---|---|---|
| `eligible` | levels `[1, 2]`, level 2, 0 prior, no open | `[]` |
| `not-on-roster` | `None` | `[NOT_ON_ROSTER]` |
| `empty-roster-entry` | `[]`, level 1 | `[LEVEL_NOT_PERMITTED]` — **not** `NOT_ON_ROSTER` |
| `level-not-permitted` | `[1]`, level 2 | `[LEVEL_NOT_PERMITTED]` |
| `first-retest-allowed` | 1 prior, practical | `[]` |
| `second-retest-refused` | 2 prior, practical | `[RETEST_USED]` — **1 and 2 together pin the boundary**; `> 2` and `>= 1` both die |
| `theory-has-no-retest-limit` | 5 prior, theory | `[]` |
| `already-enrolled` | open sitting | `[ALREADY_ENROLLED]` |
| `every-refusal-at-once` | `None`, 2 prior, open, practical | all three — kills an early `return` |

Assert the **list**, compared as a set or in a fixed order you document — not `len(...)`.

Subject: `feat(exams): add the enrolment eligibility rule (§2.7)`

**Review gate.** Mutants: `>= 2` → `> 2`; `>= 2` → `>= 1`; drop `exam_is_practical`; `None`
check → falsiness check (`if not roster_levels`, which conflates the two absences); early
return after the first refusal.

---

## Task 4: `enrol`, and the two fields it writes

**Files:**
- Modify: `exams/models/sitting.py`
- Create: three migrations (see Step 2), `exams/enrolment.py`, `tests/exams/test_enrolment.py`

**Interfaces:**
- Consumes: `refusals`, `Refusal`, `Cycle.objects.for_year`, `RosterEntry`,
  `user.judge_profile`.
- Produces: `Sitting.candidate_number: str`, `Sitting.override_by`, `Sitting.override_reason`;
  `enrol(judge: User, exam: Exam, *, official: User, override_reason: str | None = None) ->
  Sitting`; `EnrolmentRefused(refusals: list[Refusal])`, `JudgeHasNoProfile`.

- [ ] **Step 1: Write the failing tests** — the table below

- [ ] **Step 2: `candidate_number`, in three migrations**

A `CharField` with a callable default, e.g. `default=new_candidate_number` returning
`secrets.token_hex(4).upper()`, and `UniqueConstraint(fields=["exam", "candidate_number"])`.

**Django evaluates a callable default once for all existing rows during `AddField`** — every
existing sitting would get the same number and the unique constraint would refuse the
migration. This is documented: Django's how-to *"Migrations that add unique fields"*. Follow
it exactly — (1) add the field `null=True` with no constraint, (2) a `RunPython` that gives
each existing row its own number, (3) alter to non-null and add the constraint. The test
database starts empty, so **only your dev database** will show the failure if you skip this;
that is why it is written down.

Not the `pk`: it is sequential and reveals enrolment order, which is what review-by-number
exists to hide (§2.2.1).

- [ ] **Step 3: the override pair**

`override_by` a nullable FK to `AUTH_USER_MODEL`, `related_name="overrides_made"`,
`PROTECT`. `override_reason` a `TextField(blank=True)`. One `CheckConstraint`:

```
(override_by IS NULL AND override_reason = '')
OR (override_by IS NOT NULL AND override_reason <> '')
```

— expressed with `Q` objects. The second clause is the spec's *"a blank reason field is
worse than none"*.

- [ ] **Step 4: Write `enrol`**

Inside `transaction.atomic()`: fetch the profile with
`JudgeProfile.objects.select_for_update().get(user=judge)` — `DoesNotExist` becomes
`JudgeHasNoProfile`. Then gather `refusals()`' inputs:

- `roster_levels`: the `RosterEntry` for `(profile.sagf_id, exam.year)`'s `levels`, or
  `None` when absent — `filter(...).first()`, then `None` check;
- `prior_practical_sittings`: this judge's sittings whose exam is `PRACTICAL` and whose
  `exam__year` falls in `Cycle.objects.for_year(exam.year)`'s range;
- `has_open_sitting`: a `PENDING` or `IN_PROGRESS` sitting for this exam.

**Strip `override_reason` first**, then treat `""` as no override. Raise
`EnrolmentRefused(refusals)` when refusals remain and there is no reason. Otherwise create the
sitting, with `override_by=official` only when there were refusals to override — an override
recorded on an eligible enrolment is noise in the audit trail.

| test | asserts |
|---|---|
| `test_an_eligible_judge_is_enrolled` | returns a `PENDING` sitting; re-read by pk; `override_by_id is None` |
| `test_an_ineligible_judge_is_refused_with_reasons` | `EnrolmentRefused` whose `.refusals` equals `[NOT_ON_ROSTER]`, **and** `Sitting.objects.count() == 0` — `count()` is satisfied by emptiness, so this is paired with the positive `eligible` test above using the same fixtures |
| `test_an_override_records_who_and_why` | refused judge, `override_reason="Medical certificate on file"`; re-read; `override_by_id == official.pk`, reason stored |
| `test_a_blank_override_is_no_override` | `override_reason="   "` still raises `EnrolmentRefused` — pins the strip |
| `test_a_judge_without_a_profile_cannot_be_enrolled` | `JudgeHasNoProfile`, even **with** an override reason |
| `test_the_retest_limit_counts_across_the_cycle` | two practical sittings on **different exams in the same cycle** (2025 and 2027), then a 2028 enrolment is refused; a 2029 one is not. Different exams is the point — a count by `exam=` would pass the same-exam version |
| `test_candidate_numbers_differ_within_an_exam` | enrol two judges; numbers differ. **Weak on its own** — random numbers almost always differ; the constraint mutant in the migration is what really pins uniqueness |
| `test_the_override_constraint_refuses_a_reason_without_an_official` | `objects.create(..., override_reason="x")` with no `override_by` raises `IntegrityError` |

`select_for_update()` here has **no single-threaded mutant that reaches it**. Record it in the
catalogue's comments as untested-by-design, per the `mutation-sweep` skill, rather than
hunting one.

Subject: `feat(exams): enrol judges against the roster, with recorded overrides`

**Review gate.** Mutants: drop the strip; override recorded on eligible enrolments; count by
`exam=` instead of cycle; the migration's unique constraint and check constraint.

---

## Task 5: Freeze the component's aspect onto items and results

**Files:**
- Modify: `exams/models/sitting.py`, `exams/freeze.py`, `exams/marking.py`
- Create: generated migration
- Test: `tests/exams/test_freeze.py`, `tests/exams/test_results.py`

**Why this task exists** (found 2026-09-25 while writing this plan). Difficulty is
`mean(DA, DB)`, so certification must find the `DA` and `DB` results. `ComponentResult`
holds `component_name`, `component_position`, `percentage` and `grade_name` — no aspect.
Finding `DA` by **name** is F2's shape: the marking table was frozen onto items precisely to
avoid a lookup by frozen name, and there is no unique constraint on `(exam, name)`. Finding it
by **position** assumes an order nothing enforces. So the aspect is copied, like the name.

**Interfaces:**
- Produces: `SittingItem.component_aspect: str` (`""` for theory),
  `ComponentResult.aspect: str`.

- [ ] **Step 1: Write the failing tests**

- [ ] **Step 2: Add the fields, freeze and carry them**

`component_aspect` a `CharField(max_length=2, blank=True)` — `""` for theory, matching
`ExamComponent.aspect`. Existing rows: a plain default of `""` is correct for theory sittings
and **wrong for practical ones**, so if your dev database holds practical sittings, fill them
in a `RunPython` from their component; otherwise say in the migration that none existed. The
freeze copies `component.aspect`; `submit_sitting` copies it from the group's first item onto
the result, as it already does the name.

| test | asserts |
|---|---|
| `test_a_frozen_item_carries_its_component_aspect` | freeze a two-component practical exam (`DA`, `EX`); every item's `component_aspect` matches its component — **two aspects**, so a mutant freezing a constant dies |
| `test_a_component_result_carries_its_aspect` | submit; each result's `aspect` equals its component's, re-read |

Subject: `feat(exams): freeze the component aspect onto items and results`

**Review gate.** Mutants: freeze `""` instead of the aspect; results copy the aspect from the
wrong group.

---

## Task 6: Dimension grades and the examination category — pure

**Files:**
- Create: `exams/awards.py`, `tests/exams/test_awards.py`

**Interfaces:**
- Consumes: `scoring.score_component`, `scoring.grade`, `scoring.GradeBand`.
- Produces:

  ```python
  class Category(enum.IntEnum): ONE = 1; TWO = 2; THREE = 3; FOUR = 4; FAIL = 5
  @dataclass(frozen=True) class AspectResult: percentage: Decimal; grade: str; bands: tuple[GradeBand, ...]
  def dimension_grades(results: Mapping[str, AspectResult]) -> dict[str, tuple[str, tuple[GradeBand, ...]]]
  def examination_category(dimensions, requirements: Mapping[tuple[int, str], str]) -> Category
  class BandsDisagree(ValueError), class UnknownGrade(ValueError)
  ```

  `results` is keyed by aspect (`"DA"`, `"DB"`, `"AV"`, `"EX"`); `dimension_grades` returns
  `{"DIFFICULTY": ..., "EXECUTION": ..., "ARTISTRY": ...}`, each a grade name with the band
  set that ranks it. `requirements` is keyed by `(category, dimension)`.

**`FAIL = 5`, not `0`, deliberately.** Category 1 is best, so "worse" is "numerically
greater" everywhere: the floor is `previous + 2`, the cap is `min(...)` in numbers, and FAIL
sorts after 4 with no special case. `FAIL = 0` would put it *above* Category 1 in every
comparison — a wrong answer with no error.

**No Django import.** `scoring` only.

- [ ] **Step 1: Write the failing tests** — both tables

- [ ] **Step 2: `dimension_grades`**

Difficulty: `score_component([DA.percentage, DB.percentage])` — `scoring`'s own mean,
quantized `ROUND_HALF_UP`, over the two **stored, rounded** percentages (decided 2026-08-08).
Grade it with `grade(percentage=..., bands=DA.bands)`. **If `DA.bands != DB.bands`, raise
`BandsDisagree`.** Execution and Artistry are the `EX` and `AV` grades as stored.

- [ ] **Step 3: `examination_category`**

A grade's **rank** is its index in its band set sorted by `minimum` — `Fail` 0, `Pass` 1 and
so on. For each category from `ONE` to `FOUR`, it is met when every dimension's rank is at
least the rank of that cell's `minimum_grade` in the same band set. Return the first met, else
`FAIL`. A `minimum_grade` not present in the band set raises `UnknownGrade` — a typo in the
§2.6 table must not silently rank as nothing.

The construct for rank is `next(i for i, band in enumerate(sorted(bands, key=...)) if
band.name == name)` or a dict built once; either way, **never `>` on the names**.

| `dimension_grades` test | asserts |
|---|---|
| `difficulty-is-the-mean-of-the-rounded-scores` | DA `79.90`, DB `80.09` → Difficulty graded at `80.00` → **Excellent** against an 80 floor. The CLAUDE.md example; averaging unrounded values would give Very Good |
| `difficulty-rounds-half-up` | DA `79.98`, DB `79.99` → mean `79.985` → **`79.99`**. Half-even gives `79.98`, so this pair separates the two modes; `79.99`/`80.00` does not — both give `80.00` (verified 2026-09-25, `score_component` included). Assert the percentage itself, not only the grade |
| `execution-and-artistry-are-read-as-stored` | EX and AV grades pass through unchanged — use **different** grades for the two so a swap dies |
| `differing-difficulty-bands-raise` | DA and DB with different band sets → `BandsDisagree` |

| `examination_category` test | asserts |
|---|---|
| `category-1` | D Excellent, E VG, A VG → `ONE` |
| `category-1-asymmetry` | D **VG**, E Excellent, A Excellent → **`TWO`** — the only row that is not uniform; a uniform-table mutant survives every other case |
| `weakest-dimension-caps` | D Excellent, E Excellent, A Good → `THREE` |
| `category-4` | all Pass → `FOUR` |
| `fail` | one Fail → `FAIL` |
| `ranks-not-names` | a case where name order and rank order disagree — `"Pass" > "Good"` as strings — decides the result |
| `unknown-minimum-grade-raises` | `minimum_grade="Excelent"` → `UnknownGrade` |

**Build the §2.6 requirements and the two band sets as fixtures in the test module**, from the
tables in the original spec. They are synthetic in the sense that matters — FIG publishes them
— and they are the only way these tests mean anything.

Subject: `feat(exams): derive the examination category from four grades (§2.6)`

**Review gate.** Mutants: compare names instead of ranks; average unrounded; grade Difficulty
against DB's bands without the check; return the *last* category met; `FAIL = 0`.

---

## Task 7: The award bounds — pure

**Files:**
- Modify: `exams/awards.py`, `tests/exams/test_awards.py`

**Interfaces:**
- Produces:

  ```python
  @dataclass(frozen=True) class PriorCertification: cycle_first_year: int; category: Category
  @dataclass(frozen=True) class Bounds: floor: Category | None; cap: Category | None; suggested: Category
  def award_bounds(*, examination: Category, history: Sequence[PriorCertification],
                   cycle_first_year: int, previous_cycle_first_year: int) -> Bounds
  ```

  `history` is every earlier certification, imported or examined; the service builds it.

- [ ] **Step 1: Write the failing tests**

- [ ] **Step 2: Write `award_bounds`**

- **cap** = `THREE` when `history` has nothing from a cycle before this one; else `None`.
- **floor** = the latest certification from the **previous** cycle; if it is `ONE` or `TWO`,
  floor = it `+ 2`; otherwise `None` (a previous 3, 4 or FAIL has no floor; no certification
  in the previous cycle — §2.8 interruption — has no floor).
- **suggested** = `examination`, made no better than `cap` (`max` in numbers) and no worse
  than `floor` (`min` in numbers).

"Latest" in the previous cycle is **the last one recorded**, not the best — §2.7's "valid and
final" again. The service passes `history` in recording order; say so in the docstring.

| test | asserts |
|---|---|
| `first-cycle-cap` | no history, exam `ONE` → cap `THREE`, suggested `THREE` |
| `imported-history-lifts-the-cap` | one imported `TWO` last cycle, exam `ONE` → cap `None`, suggested `ONE` |
| `floor-on-pass` | previous `ONE`, exam `FOUR` → floor `THREE`, suggested `THREE` — **the case the original spec's `min()` got wrong** |
| `floor-on-fail` | previous `TWO`, exam `FAIL` → suggested `FOUR` (§2.6 "passing or failure") |
| `no-floor-from-category-3` | previous `THREE`, exam `FAIL` → floor `None`, suggested `FAIL` |
| `no-floor-after-interruption` | only certification two cycles back → floor `None` |
| `latest-not-best-in-the-previous-cycle` | previous cycle holds `ONE` then `THREE`, in that order → floor from `THREE`, i.e. `None` |
| `floor-and-cap-never-coexist` | **exhaustive**: every `Category` × history shapes {none, previous-cycle only, older only, both} — assert `not (floor and cap)` for all. `itertools.product` inside the test, not `parametrize` — 20 cases of one property is one test |

Subject: `feat(exams): bound the award by first cycle and drop limit (§2.6)`

**Review gate.** Mutants: floor as a cap (`max`↔`min` swapped — the original spec's bug); `+ 2`
→ `+ 1`; floor from the best rather than the latest; cap ignores imported rows; floor from any
earlier cycle rather than the previous one.

---

# Part B — certification, imports and the admin

## Task 8: `Certification`, and `Sitting` loses its certification fields

**Files:**
- Create: `exams/models/certification.py`, generated migration(s)
- Modify: `exams/models/__init__.py`, `exams/models/sitting.py` (`__str__` included)
- Modify: `tests/exams/test_sitting.py` — **delete**
  `test_certifying_records_who_and_when`; its subject no longer exists on `Sitting`
- Modify: `tests/exams/test_admin.py` — drop `outcome`, `certified_by`, `certified_at_0/1`
  from the sitting-change payload; with `SittingAdmin` view-only they were already inert
- Create: `tests/exams/test_certification.py`

**Interfaces:**
- Produces: `Certification(judge: JudgeProfile, cycle: Cycle, category: int, source: Source,
  sitting: Sitting | None, examination_category, suggested_category, floor, cap: int | None,
  reason: str, certified_by: User, certified_at)`; `Source.EXAM | IMPORTED`. Categories are
  stored as the `Category` integer values, 1–5.

- [ ] **Step 1: Write the failing tests**

- [ ] **Step 2: The model**

`sitting` a `OneToOneField(Sitting, null=True, PROTECT, related_name="certification")` —
one-to-one gives the uniqueness the spec asks for. `HistoricalRecords()` is **not** needed:
the rows are immutable, so history would record creation only. Say so in a comment.

Constraints, each a `CheckConstraint` named `ck_certification_…`:

1. `source = EXAM` ⇔ `sitting IS NOT NULL`
2. `IMPORTED` ⇒ `examination_category`, `suggested_category`, `floor`, `cap` all `NULL`, and
   `reason <> ''`
3. `EXAM` ⇒ `examination_category` and `suggested_category` not null, and
   (`category = suggested_category` **or** `reason <> ''`)
4. every category column, where not null, between 1 and 5

- [ ] **Step 3: Remove `certified_at`, `certified_by`, `outcome` from `Sitting`**

Two copies of who certified can disagree and nothing reconciles them. Fix `__str__`, which
reads `certified_by`.

| test | asserts |
|---|---|
| `test_an_exam_certification_needs_a_sitting` | `source=EXAM`, `sitting=None` → `IntegrityError` |
| `test_an_imported_certification_has_no_sitting` | `source=IMPORTED` with a sitting → raises |
| `test_an_imported_certification_needs_a_reason` | `IMPORTED`, `reason=""` → raises |
| `test_an_imported_certification_computes_nothing` | `IMPORTED` with `examination_category=2` → raises |
| `test_departing_from_the_suggestion_needs_a_reason` | `EXAM`, `category=2`, `suggested=3`, `reason=""` → raises; the same with a reason saves — **both halves**, so the constraint is shown to discriminate rather than refuse everything |
| `test_following_the_suggestion_needs_no_reason` | `category == suggested`, blank reason, saves |
| `test_a_sitting_is_certified_once` | a second certification for one sitting raises |

Subject: `feat(exams): record certifications as an immutable log`

**Review gate.** One migration mutant per check constraint, flipping or dropping its
condition. The `both-halves` test is the one that must kill "reason always required".

---

## Task 9: `certify`

**Files:**
- Create: `exams/certification.py` (service)
- Modify: `tests/exams/test_certification.py`

**Interfaces:**
- Consumes: `dimension_grades`, `examination_category`, `award_bounds`, `Cycle.for_year`,
  `CategoryRequirement`, `grade_bands_from_json`.
- Produces: `certify(sitting: Sitting, *, official: User, category: Category, reason: str = "")
  -> Certification`; exceptions `SittingNotSubmitted`, `NotAPracticalSitting`,
  `ResultsIncomplete`.

- [ ] **Step 1: Write the failing tests — one per guard first**, each shown red by deleting
  its guard

- [ ] **Step 2: Write `certify`**

Inside `transaction.atomic()`, re-read the sitting with `select_for_update().get(pk=...)` —
**never trust the instance you were handed**; Task 8 of the exams plan shipped a bug from a
cached related object. Then, in order:

1. guards: `SUBMITTED`; exam `PRACTICAL`; results for all four aspects `DA DB AV EX` exist;
2. build `AspectResult`s from `sitting.results` and each aspect's frozen bands — read from the
   first item with that `component_aspect`, through `grade_bands_from_json`;
3. requirements for `Cycle.for_year(exam.year)` into the `(category, dimension)` mapping;
4. history: the judge's **other** certifications in recording order, as `PriorCertification`s;
5. `award_bounds(...)`, then create the `Certification` with every computed value stored, and
   set `status = CERTIFIED`.

Strip `reason` before saving, for the same reason as `enrol`.

`certify` reads the category table **live** at certification time. That is correct here, not
an F2 window: certification *is* the recording event, and everything computed from the table
is stored on the row it produces.

| test | asserts |
|---|---|
| `test_an_unsubmitted_sitting_cannot_be_certified` | `SittingNotSubmitted`; nothing created |
| `test_a_theory_sitting_cannot_be_certified` | `NotAPracticalSitting` |
| `test_a_sitting_missing_a_result_cannot_be_certified` | delete the `AV` result first → `ResultsIncomplete` |
| `test_certifying_stores_what_the_official_saw` | an end-to-end practical sitting with known grades; re-read the certification; assert `examination_category`, `floor`, `cap`, `suggested_category` **as literals** — "assert the value, not that two values differ" |
| `test_certifying_marks_the_sitting_certified` | re-read the sitting; `CERTIFIED` |
| `test_the_same_sitting_object_cannot_be_certified_twice` | certify, then certify the **same instance** again → `SittingNotSubmitted`; the same-object rule from the exams plan's Task 8 |
| `test_history_is_the_judge_s_own` | another judge's `ONE` last cycle does **not** lift this judge's first-cycle cap |

Subject: `feat(exams): certify a submitted practical sitting`

**Review gate.** Mutants: each guard deleted; history filtered on nothing; the instance's
status read instead of the locked row's; the frozen bands replaced by live ones.

---

## Task 10: Roster import

**Files:**
- Create: `accounts/roster.py`, `tests/accounts/test_roster.py`
- Modify: `accounts/admin.py` — an upload view, a preview, a confirm

**Interfaces:**
- Produces: `parse_roster(rows: Iterable[Mapping[str, str]], *, year: int) ->
  tuple[list[RosterRow], list[RowError]]`; `diff_roster(existing: Mapping[str, RosterRow],
  incoming: Sequence[RosterRow]) -> RosterChanges(add, change, remove)`;
  `apply_roster(changes, *, year, official)`; `RosterChanged` when apply's recomputed diff
  differs from the previewed one.

`parse_roster` and `diff_roster` are pure — plain dataclasses in, plain dataclasses out.
`csv.DictReader` produces the rows; the view does that, the functions never see a file.

- [ ] **Step 1: Write the failing tests** — parse and diff first, no database

- [ ] **Step 2: `parse_roster`, `diff_roster`**

Levels arrive as `"1;2"` — **semicolon**, because a comma is the CSV delimiter. Lowercase the
email. A duplicate `sagf_id` or any malformed row is a `RowError`, and **any error rejects the
whole file** in the view.

- [ ] **Step 3: `apply_roster`**

One `transaction.atomic()`. Recompute the diff against the database and compare with the
preview; if they differ, raise `RosterChanged` and write nothing. Create, update and delete
through the ORM row by row — **not `bulk_create`/`bulk_update`**, which send no signals, and
`RosterEntry` is history-tracked.

- [ ] **Step 4: The admin view**

A custom admin URL via `get_urls()`: upload form → preview listing adds, changes, removes and
errors → confirm button. Keep the previewed diff in the session between the two requests.

| test | asserts |
|---|---|
| `test_a_valid_row_parses` | one `RosterRow` with lowercased email and `[1, 2]` |
| `test_a_duplicate_sagf_id_is_an_error` | two rows, one `sagf_id` → a `RowError` naming it; **not** last-wins |
| `test_a_malformed_level_is_an_error` | `"1;x"` → error |
| `test_the_diff_finds_adds_changes_and_removes` | existing A, B; incoming B-changed, C → add C, change B, remove A — **all three in one test** so a mutant swapping two of them dies |
| `test_an_unchanged_row_is_not_a_change` | same row both sides → empty diff |
| `test_a_dry_run_writes_nothing` | preview via the admin; `RosterEntry.objects.count()` unchanged **and** the preview listed at least one add — the positive control, because `count()` is satisfied by emptiness |
| `test_apply_refuses_a_stale_preview` | preview, then edit a row directly, then apply → `RosterChanged`, and the direct edit survives |
| `test_apply_records_history` | after apply, the changed entry's `history.count()` is 2 — kills a `bulk_update` mutant |

Subject: `feat(accounts): import the yearly roster with a dry run`

**Review gate.** Mutants: last-wins on duplicates; `bulk_update`; drop the stale check; the
view writing during preview.

---

## Task 11: Category import

**Files:**
- Create: `exams/category_import.py`, `tests/exams/test_category_import.py`
- Modify: `exams/admin.py`

**Interfaces:**
- Consumes: the parse / diff / apply shape of Task 10.
- Produces: `parse_categories`, `diff_categories`, `apply_categories(changes, *, cycle,
  official)`.

Columns `sagf_id`, `category`. The cycle is chosen in the upload form — one file per cycle.
Apply creates a `JudgeProfile` with `user=None` where none exists, and a
`Certification(source=IMPORTED, reason=f"Imported from the SAGF register, {date}")`.

**"Change" and "remove" do not exist here.** Certifications are immutable: re-importing a
judge whose imported category differs is a **new row** superseding the old, and a judge
missing from the file keeps their history. So the diff has *add* and *supersede* only. Say so
in the preview.

| test | asserts |
|---|---|
| `test_an_import_creates_a_judge_without_a_login` | unknown `sagf_id` → a profile with `user_id is None` and one `IMPORTED` certification |
| `test_an_import_reuses_an_existing_profile` | known `sagf_id` → no second profile |
| `test_reimporting_the_same_category_changes_nothing` | apply twice → one certification |
| `test_a_different_category_supersedes` | apply `TWO`, then `ONE` → two rows, latest `ONE` |
| `test_a_missing_judge_keeps_their_history` | file without judge X → X's certification untouched |
| `test_category_five_in_the_file_is_an_error` | `"5"` → `RowError` — FAIL is not importable as a current category |
| `test_a_dry_run_writes_nothing` | as in Task 10, with its positive control |

Subject: `feat(exams): import current categories from the SAGF register`

---

## Task 12: The admin — enrolment, review by number, certification

**Files:**
- Modify: `exams/admin.py`, `tests/exams/test_admin.py`

- [ ] **Step 1: Write the failing tests**

- [ ] **Step 2: Enrolment form** — a custom admin view: judge, exam, optional override
  reason. On `EnrolmentRefused` it re-renders listing the refusals, and the reason field is
  how the official overrides.

- [ ] **Step 3: Review list** — submitted practical sittings, showing `candidate_number`, the
  four grades, examination category, floor, cap and suggestion. **No judge name, no username,
  no email** — and not in the page title or a link's `title` either.

- [ ] **Step 4: Certify form** — per sitting: category (defaulting to the suggestion) and
  reason. On save, the judge's name appears.

| test | asserts |
|---|---|
| `test_the_review_list_hides_the_judge` | judge named `Zebedee Quibble-Farnsworth` — **distinctive**, per the rendered-page rule; assert the name, the username and the email are all **absent** while the candidate number is **present** |
| `test_the_name_appears_once_certified` | certify through the form; the name is now present — the absent-then-present pair |
| `test_the_enrolment_form_lists_refusals` | an off-roster judge; the page contains the refusal's display text and no sitting was created |
| `test_the_enrolment_form_overrides_with_a_reason` | POST with a reason; one sitting, `override_by` set |
| `test_certification_views_require_staff` | a **signed-in non-staff** user is refused — anonymous would pass against `login_required` too (the questions plan's Task 9 lesson) |

Subject: `feat(exams): enrol and certify through the admin, reviewing by number`

---

## Task 13: Sweep and plan close

- [ ] Full sweep, suite, lint:

```bash
../.venv/bin/python tools/mutation_sweep.py
../.venv/bin/python -m pytest -q && ../.venv/bin/ruff format . && ../.venv/bin/ruff check .
```

Expect zero survivors, bar `select_for_update` in `enrol` recorded as unreachable. Then
Claude updates `CLAUDE.md`: state block, next action (Plan 2, sign-in), and the spec
corrections now having tests — `floor-on-pass` is the executable form of the `min()`
correction.

---

## Open questions this plan raises

1. **Provisional bands.** §2.2.1: the TC fixes the grade scale *after* the first course, then
   applies it for the cycle. Bands are frozen at `start_sitting`, so the first cohort of a
   cycle would be graded against whatever bands existed when they started — possibly
   provisional ones. Whether SAGF re-grades that cohort, and how, is for SAGF; the design
   question is whether `certify` should ever regrade from live bands. Today it does not.
2. **Online-examination cap** (§2.3, Category 4 maximum) — carried from the spec.
3. **The experience window** (§2.6, two years into the new cycle) — carried from the spec.
