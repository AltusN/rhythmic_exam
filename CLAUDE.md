# Rhythmic Exam — working notes for Claude

## How to work here — read this first

**Altus writes all the implementation code. You do not.**

He asked to be tutored through this rebuild step by step, and explicitly asked you
to be **stern** about holding him to it. The goal is that he understands the stack
at the end, not that the app gets built fast. Code you write is code he doesn't
learn.

- Explain the concept and the *why*, then hand him the keyboard.
- Small snippets to illustrate a pattern are fine. Whole files and whole features
  are not.
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

## Read these before doing anything

- `docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md` — the design.
  Includes eight numbered findings (F1–F8) from the old app; each one is a bug the
  rebuild must fix, and several have tests written specifically to pin them.
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
reading the log. There is no `commit-msg` hook yet either — the convention is
currently held by discipline alone.

## Current state

Tasks 1–3 of the scoring plan are done, plus tooling. As of 2026-08-02:

- `c0839c5` — package skeleton, editable install, smoke test.
- `58e94d8` — `scoring/values.py`, fixes F3. `to_decimal` returns `None` for blank,
  whitespace-only and `None`; raises `UnparseableAnswer` for garbage **and** for
  non-finite values (`nan`, `Infinity`, which `Decimal` otherwise accepts happily).
  A blank is the candidate's own choice; unreadable input is a fault someone must
  see. Conflating them hides data errors in results.
- `b3bb4f2` — ruff.
- `ea791b9` — `scoring/types.py` and `scoring/tables.py`, fixes F4. `BandRow` and
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
  fix `ea791b9` should have carried, and the test coverage flagged as missing: the
  below-every-bound fallback in `floor_band_index`. That test needs its own table
  whose lowest bounds are above zero, because the shared fixture starts at `0.0` and
  cannot reach the branch. It guards a real regression — rewriting the walk as
  `bisect_right(bounds, value) - 1` returns `-1`, which indexes from the end and
  awards the *top* band to a candidate who scored below the bottom one. Verified by
  mutation, not by argument.

32 tests pass and `ruff check .` is clean. Run both from `rhythmic/`. **`ruff check`
and `ruff format` are separate commands** — a clean `check` says nothing about
formatting, and that gap cost several review rounds on Task 3.

**Next action is Task 4**: `scoring/marking.py` — `mark_choice` and `mark_numeric`.
Tests first, and Step 1 moves the table fixture into `tests/conftest.py` so Tasks 3
and 4 share it. `mark_numeric` should stay thin: `to_decimal`, `abs()`, `lookup`.
Arithmetic accumulating there means logic that belongs in `tables.py`, which is what
the review gate looks for. `UnparseableAnswer` must propagate rather than mark zero.

Each task in the plan ends at a **review gate**. He posts the code; you review it
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

**Never run ruff from the repo root.** There is no config file there, so it falls
back to defaults and walks `legacy/` — and `ruff format` rewrites in place. Run it
from `rhythmic/`.

`ruff check --fix` is not safe to run blind. It once offered to delete the only
import in the smoke test, which would have left a test that passes even when the
package is broken. Read the findings before fixing.

## Open questions, both non-blocking

1. Which Code of Points cycle the SAGF national exam actually follows. The old
   answer key uses `D1 + D2` / `D3 + D4` / `AV` / `EX`, which is 2017–2020
   structure. Affects what table data gets loaded, not the design.
2. Candidates per sitting. Assumed tens.
