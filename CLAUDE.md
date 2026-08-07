# Rhythmic Exam — working notes for Claude

## How to work here — read this first

**Altus writes all the implementation code. You do not.**

He asked to be tutored through this rebuild step by step, and explicitly asked you
to be **stern** about holding him to it. The goal is that he understands the stack
at the end, not that the app gets built fast. Code you write is code he doesn't
learn.

- Small snippets to illustrate a pattern are fine. Whole files and whole features
  are not.
- **Concrete first, theory on demand.** Open with what the file contains and what to
  type. Keep the derivation for the review, or for when he asks for it. Task 6
  stalled because two pages on `hasattr`-versus-top-level-import arrived before he
  knew what `__init__.py` was supposed to hold; restating it as "two small files,
  here is what goes in each" unstuck him in one message. The reasoning was right and
  the ordering was wrong.
- **Name the mechanics explicitly.** Asked where he gets stuck (2026-08-05) he said
  turning a described shape into code, and knowing which Python or pytest construct
  to reach for — not the concepts. So say the construct: `max(..., key=...)`, the
  flat-list form of `parametrize`, `Decimal.quantize`. One line, in isolation or on
  unrelated content, is a snippet and not a solution. He still writes the file.
- If he asks you to "just write it" out of impatience, **decline and hand it back.**
  He pre-authorised you refusing that.
- **Push back on his ideas** with concrete technical reasoning. Disagreement is the
  requested behaviour, not friction to smooth over. If he argues back and he's
  right, change your mind and say so plainly.
- Go one step at a time. Confirm understanding before moving on.

**Label the basis of every claim** — *derived* or *conventional*.

Derived means you can name the mechanism and the wrong output it produces: "walk
this input through the function and it returns the top band instead of the bottom
one." Conventional means it holds because it was agreed: the commit prefixes, the
ruff rule set, parametrize-with-`ids` over a wall of asserts. There is no deeper
truth under `test(scoring):`.

Say which one you're giving him, because he should treat them differently. Argue
the derived ones on the mechanism — if his counter-argument breaks it, fold. Don't
defend the conventional ones at length; they're taste and consistency, and he can
take or leave them.

Default to precedent everywhere else — re-deriving blank-line placement is waste.
Spend the derivation where a wrong answer reaches a real candidate: the scoring
arithmetic, the band edges, the pass/fail boundary. F5 is what a good analogy
looks like when nobody re-derives it — marks are numbers, numbers sum, and the
total got called a percentage.

**When a derivation of yours is load-bearing, execute something.** You can produce
a confident derivation that is really a rationalisation of the conventional answer
you'd already picked. Running the mutation caught the `bisect_right - 1` bug for
real; asserting it would have been a guess in the same words.

**Genuine exceptions** — do these yourself, they have no teaching value:
chores (moving files, deleting things), generated migrations, and reviewing or
debugging code he has already written.

## What this is

An online certification exam for SAGF rhythmic gymnastics judges. Real candidates,
real pass/fail decisions that must hold up if disputed. Being rebuilt from scratch
as of 2026-07-28.

Nothing is scheduled, so there is **no production pressure** — build in the right
order rather than racing a date.

**Two components.** *Theory* is multiple choice, testing the rules knowledge a judge
is meant to have — `mark_choice` scores it, and `score_component` over those marks
reproduces the legacy theory percentage exactly. *Practical* is numeric, the
candidate's score against an expert's — `mark_numeric` scores it. Legacy got theory
right and practical wrong: `calculate_theory_score` divided by the question count,
`calculate_practical_score` summed marks and called the total a percentage (F5).

**Theory questions are banded by level, cumulatively.** A level 2 candidate sits
every level 1 question plus the level 2 additions; level 3 sits all three bands, and
so on. So a question carries the *lowest* level obliged to answer it, and selection
is `question.minimum_level <= candidate.level` — a lower-bound comparison, the same
shape as `GradeBand.minimum` and `floor_band_index`. Modelling it as
`question.level == candidate.level` looks reasonable and silently hands a level 3
candidate only the level 3 additions, sitting them a fraction of their exam. That is
exactly what the old app did — see **F9**.

**Decided 2026-08-05: a question exists once; a paper lists which questions it
contains.** Each level's paper is explicit data — a many-to-many, not a scalar
`level` column and not a `minimum_level <= candidate.level` query. Overlap between
levels is the same question row referenced by two papers, never a copy of it.

Two things this buys, and both were argued rather than assumed. Duplicating a
question per level means an answer-key correction has to find every copy, and a
missed copy leaves two cohorts marked against different keys with no error anywhere
— F1's family. And a pure cumulative rule cannot express a level that *drops* or
replaces an inherited question; the first time the syllabus does that you bolt on an
exceptions table and arrive at the join table by a worse road.

"Cumulative" therefore describes how a paper is **built** — seed level 2 from level
1, then add — not how it is queried. Note the usual reason to duplicate does not
apply here: keeping historical papers stable is F1's snapshot's job, so duplication
buys nothing there. The exact schema is for the questions-app plan.

**Not every level sits every component.** Some levels are theory-only — there is no
practical paper for them at all. So the components a candidate sits are a property
of their level, not a constant, and a result record must distinguish *not
applicable* from *scored zero*. Carrying an absent practical as `0` turns a 90%
theory-only candidate from Excellent into Fail on a straight average. This is the
same distinction `to_decimal` already draws between a blank answer and an
unreadable one (F3): absence is not a value. `score_component([])` raising rather
than returning `0` is the existing half of that guard; the other half belongs in
whatever combines components, which is not built yet.

## Read these before doing anything

- `docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md` — the design.
  Includes ten numbered findings (F1–F10) from the old app; each one is a bug the
  rebuild must fix, and several have tests written specifically to pin them. F1–F8
  came from the original audit; **F9 and F10 were found on 2026-08-05** while
  checking how legacy selected questions by level. Assume there are more.
- `docs/superpowers/plans/2026-07-28-scoring-package.md` — the current plan.

## Layout

```
docs/superpowers/{specs,plans}/
rhythmic/     the new system. Paths in the plan are relative to HERE.
legacy/
  flask_backend/    the 2023 Flask app. Reference only. Do not modify or run.
```

`legacy/` is kept for exactly two things: the exam media (117 images, 10 videos)
and the type 1–5 templates to check new rendering against. **It gets deleted when
the media is migrated and the block renderers are built** — that condition was
agreed, so don't let tidiness pull the trigger early, and don't propose building on
it either.

The FastAPI backend was deleted on 2026-07-28 (recoverable from `4e6aa1b`,
`206ff42`). Don't suggest reviving it.

## Spelling

The sport is *rhythmic*. The legacy tree and the old package spell it *rhytmic*.
The repo itself was renamed to `rhythmic_exam` on 2026-07-28. **New code uses the
correct spelling.** Don't "fix" the legacy tree, and don't propagate the typo into
new code.

## Hard constraints

- **No real exam content in this repository. It is public.** The question bank and
  answer key were removed on 2026-07-28. `legacy/flask_backend/doc/example_format.csv`
  is synthetic and safe. Before committing any data file, check whether it carries
  questions or answers. The 117 tracked exam images are a known pre-existing
  exposure, to be revisited at media migration.
- **`rhythmic/scoring/` imports nothing from Django and touches no database.** If a
  module there needs a framework, the boundary is wrong. Enforced by ruff `TID251`,
  which bans `django`, `sqlalchemy` and `flask` — see Tooling below.
- **`Decimal` everywhere for marks and deductions, never `float`. Never compare
  answers as strings** — finding F3 is exactly that bug.
- **Marking tables and grade bands are data, never literals in Python.** FIG
  republishes them every four-year cycle and doesn't finalise them until after the
  first exam is sat.
- **Check `git status` before committing.** `git commit` commits the whole index —
  this already caused a file to be committed after Altus had declined it.

## Commit messages

Conventional Commits, **starting with the first commit after `c0839c5`**. Everything
up to and including `c0839c5` predates the convention — do not rewrite those messages
to match.

```
<type>(<scope>): <imperative subject>
```

- **Types, closed set:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
  Nothing else. An unbounded type list is the same as no convention.
- **Scope** is the package or Django app: `scoring`, `questions`, `exams`,
  `accounts`, `frontend`, `docs`. Omit only when the change is genuinely repo-wide.
- **Subject:** imperative mood ("add", not "added"/"adds"), lower case after the
  colon, no trailing full stop, under ~72 characters.
- **Tests ship with the behaviour they cover**, so they are part of it —
  `feat(scoring):`, not `test:`. Reserve `test:` for tests added to code that
  already exists, which is mostly the F6 backfill.
- **The prefix does not excuse a vague subject.** `chore: project setup` is a bad
  message with a prefix on it. Say what changed.
- **Body explains why**, not what — the diff already says what. Wrap at 72.
- **Cite the finding** when a commit fixes one: `fix(scoring): compare answers as
  Decimal, not string (F3)`. The findings are the spine of the rebuild and the log
  should be searchable by them.

No release automation is wired up and none is planned; the prefixes are for humans
reading the log. There is no `commit-msg` hook — **this convention is held by
discipline alone.** The `pre-commit` hook added on 2026-08-04 enforces ruff, and
says nothing whatever about commit messages; don't mistake one for the other.

## Current state

**The scoring plan is finished — all seven tasks.** As of 2026-08-05, **81 tests
pass** and both `ruff check .` and `ruff format --check .` are clean. Run all three
from `rhythmic/`.

| file | tests |
|---|---|
| `test_values.py` | 17 |
| `test_aggregate.py` | 18 |
| `test_tables.py` | 14 |
| `test_marking.py` | 12 |
| `test_public_api.py` | 10 |
| `test_legacy_parity.py` | 9 |
| `test_smoke.py` | 1 |

**The plan's own test-count estimates are stale** — it predicts 54 by Task 6. Tasks
4 and 5 both grew cases beyond its table. Don't chase the plan's numbers; they were
written before the tests were.

- `c0839c5` — package skeleton, editable install, smoke test.
- `58e94d8` — `scoring/values.py`, fixes F3. `to_decimal` returns `None` for blank,
  whitespace-only and `None`; raises `UnparseableAnswer` for garbage **and** for
  non-finite values (`nan`, `Infinity`, which `Decimal` otherwise accepts happily).
  A blank is the candidate's own choice; unreadable input is a fault someone must
  see. Conflating them hides data errors in results.
- `b3bb4f2` — ruff.
- `83a1661` — `scoring/types.py` and `scoring/tables.py`, fixes F4. `BandRow` and
  `MarkingTable` are frozen dataclasses; `MarkingTable.lookup` is **keyword-only**,
  because both arguments are `Decimal` and a positional swap returns a plausible
  wrong percentage instead of an error. Both dimensions floor into half-open bands
  via one shared helper, `tables.floor_band_index`, which walks bounds from the top
  down — so the open-ended top band and the below-the-bottom fallback need no
  special case, and rows and columns cannot drift apart.

  `MarkingTable.__post_init__` rejects malformed tables at construction, so no
  invalid table can reach `lookup` by any path. It went beyond the plan: validating
  in `lookup` would re-answer, on every call, a question the `frozen=True` settles
  at `__init__`. Ordering is the check that matters — unsorted bounds return a real
  index and a wrong mark, where every other violation raises `IndexError`.

- `6a6b495`, `d44f694`, `89cb840` — `pytest-cov` in the `dev` extra, a `ruff format`
  fix `83a1661` should have carried, and the test coverage flagged as missing: the
  below-every-bound fallback in `floor_band_index`. That test needs its own table
  whose lowest bounds are above zero, because the shared fixture starts at `0.0` and
  cannot reach the branch. It guards a real regression — rewriting the walk as
  `bisect_right(bounds, value) - 1` returns `-1`, which indexes from the end and
  awards the *top* band to a candidate who scored below the bottom one. Verified by
  mutation, not by argument.

- `b47f480` — `scoring/marking.py`, Task 4. `mark_numeric` stays thin: `to_decimal`,
  one subtraction, `abs()`, `lookup`. Every band decision lives in `tables.py` and
  every parsing decision in `values.py`; that single subtraction is the only
  arithmetic that is marking's own business. A blank answer marks zero;
  `UnparseableAnswer` propagates rather than being caught and re-raised. Note that
  `mark_choice` has no source in the FIG rules — see Open questions.

- `f0cbc33` — `scoring/aggregate.py` plus `GradeBand`, fixes F5. Legacy summed
  per-item marks and called the total a percentage, which was correct only for
  exactly 20 items worth 5 marks each; 21 items reports 105%. `score_component` is
  the arithmetic mean, quantized to 2dp with `ROUND_HALF_UP`.

  **The rounding decision, which is the one that reaches candidates.** `grade`
  consumes the *rounded* value, so the number shown is the number that decided the
  grade, and a tie at a band floor resolves in the candidate's favour — `49.99` and
  `50.00` average to `49.995`, round to `50.00`, and pass. Grading an unrounded
  value was never available: `Decimal` division already rounds to
  `getcontext().prec`, so the real choice was 2dp deliberately or 28 significant
  digits by accident. `ROUND_HALF_UP` versus `ROUND_HALF_EVEN` cannot change a grade
  against *integer* band floors — reaching one at 2dp needs `X.995`, whose preceding
  digit is 9 and therefore odd, so half-even rounds up too — but it is pinned by a
  test regardless, because the displayed number is what a candidate re-checks by
  hand, and because FIG may publish a non-integer floor.

  `grade` selects the bands the percentage meets and takes the highest minimum,
  rather than walking a sorted list. Band ordering therefore carries no meaning and
  the loader owes no sort contract. This holds only while the minimums are distinct
  — `max` breaks ties by input order. If a `GradeScale` type ever wraps the bands,
  distinctness and sortedness are what it should validate.

- `ce6e7bd`, `9486400`, `1b5da96` — the pre-commit hook, its documentation, and the
  root `ruff.toml` guard. See Tooling.

- `a77df3b` — `scoring/__init__.py`, Task 6. Nine names re-exported with `__all__`
  asserted for **exact** equality, so a leaked name fails when it is introduced
  rather than after something imports it. Callers write `from scoring import
  mark_numeric`, never `from scoring.marking import ...`, which is what keeps
  internal modules movable. The test looks names up with `hasattr` against a list of
  strings; importing them at the top of the test module would turn a red into a
  collection error that takes the whole suite down.

- `c54d8c5` — `scoring/legacy.py` and `tests/test_legacy_parity.py`, Task 7.
  `sagf_legacy_table()` states the old SAGF scheme — 5 marks for an exact match,
  0.25 fewer per 0.05 of difference, zero at 1.00 — as a single-row `MarkingTable`
  of 21 columns. Bounds are generated with `Decimal(i) * Decimal("0.05")`, never
  `Decimal(i * 0.05)`, which multiplies in float first and puts the `0.15` bound at
  `0.15000000000000002` — dropping a candidate sitting exactly on that boundary
  into the band below.

  **The parity sweep is the deliverable, and it lives in the commit body.** Across
  every difference from 0.00 to 1.50, old and new agree on all 70 cases where the
  legacy code returned anything at all, bar one. Three divergences, all deliberate:
  F3 (`"0.3"` against expert `0.30` scored 0, now 100), F4 (**80 of the 99**
  differences that reached `diff_arr.index()` raised `ValueError`, now they floor
  into a band), and difference `0.45`, where legacy's float marks returned
  `55.00000000000001` — not a numbered finding, pinned by a test so a later sweep
  reads it as legacy's bug rather than a regression here.

  **Parity needed no real exam content.** An earlier note in this file claimed the
  data question had to be settled first; it was wrong. The comparison runs on
  synthetic difference values, not candidate answers. The legacy function was
  copied verbatim into a scratch script rather than imported, so nothing under
  `legacy/` was run — do the same for any future parity work.

**`ruff check` and `ruff format` are separate commands** — a clean `check` says
nothing about formatting. That gap cost review rounds on Tasks 3 and 5, which is
why the pre-commit hook exists.

**Next action: the scoring plan is done, so the next thing is a new plan.** The
scoring plan lists what follows, in order — the Django project and questions app,
then exams/sittings/the freeze, then accounts and the roster, then the React island
last. None of it is started and none of it is scheduled. Write the plan before
writing code; that ordering is what the whole rebuild has run on.

Each task in a plan ends at a **review gate**. He posts the code; you review it
before he starts the next task.

### Environment

The root `.venv` is the one in use, and it is now clean — Flask and SQLAlchemy are
gone, so `import flask` fails inside `scoring/` as intended. Earlier advice to build
a separate venv for `rhythmic/` is moot; don't repeat it. `rhythmic-scoring` is
installed editable, with pytest and ruff from the `dev` extra.

### Tooling

Ruff lints and formats, configured in `rhythmic/pyproject.toml`. The rule set is
chosen, not defaulted: `E W F I UP C4 B TID RET BLE SIM`, with `E501` ignored
because the formatter owns line length. `RET` and `BLE` are in because both caught
real bugs in `values.py`; ruff's stock selection would have caught neither.

**Run ruff from `rhythmic/`.** That is where the rule set lives and where the hook
runs it.

The root `ruff.toml` added on 2026-08-05 is a **guard, not a rule set** — one
`extend-exclude = ["legacy"]` line. Before it existed there was no config at the
root, so a run started there fell back to ruff's defaults and walked `legacy/`;
a stray `ruff check --fix` rewrote 25 reference files, reordering imports and
converting `.format()` calls to f-strings, `exam_utils.py` among them. Recovered
with `git restore legacy/`, since the tree was committed.

Ruff resolves the nearest config per file, so `rhythmic/` lints under its own
selection regardless of where you invoke from — the root file changes what ruff
is *allowed to reach*, never how it judges anything.

`ruff check --fix` is not safe to run blind. It once offered to delete the only
import in the smoke test, which would have left a test that passes even when the
package is broken. Read the findings before fixing.

**Formatting is enforced by a pre-commit hook**, `.githooks/pre-commit`, added on
2026-08-04 after `ruff format` was forgotten before a commit twice — once on Task 3
(`d44f694`) and once on Task 5. It runs `ruff format --check` and `ruff check` from
`rhythmic/` on the `.py` files **staged for that commit**, reports both before
aborting, and blocks rather than reformatting: a hook that edits your index puts
content in the commit you never read.

- It is **not** picked up by a fresh clone. `core.hooksPath` is local config, so
  each clone needs `git config core.hooksPath .githooks` once.
- Unstaged work in progress does not block a commit — only staged files are checked.
- It deliberately does **not** run pytest. A slow hook is a hook that gets
  `--no-verify`'d. Tests stay a separate gate.
- It checks working-tree files by path, not staged blobs, so `git add -p` on half a
  file validates content that isn't what's committed. Known and accepted; the
  `git stash --keep-index` fix can lose work when a hook exits badly.

## Open questions, none blocking

1. Which Code of Points cycle the SAGF national exam actually follows. The old
   answer key uses `D1 + D2` / `D3 + D4` / `AV` / `EX`, which is 2017–2020
   structure. Affects what table data gets loaded, not the design.
2. Candidates per sitting. Assumed tens.
3. **Resolved 2026-08-05.** `mark_choice` is an SAGF national addition, not a FIG
   one — the theory paper testing a judge's rules knowledge. See What this is for
   the level structure it implies.
4. How component percentages combine into one pass/fail. **Legacy is no help: it
   never combined them.** `main/routes.py:453-460` carries `theory` and `practical`
   side by side into the results template and the CSV, with no average, weighting or
   combined grade anywhere — a human read two numbers. So this is a decision to
   make, not a fact to recover. Whatever it is, it has to hold for levels that sit
   only one component, without F10's absent-scored-as-zero. Blocks the
   exams/sittings plan, not the questions plan.
