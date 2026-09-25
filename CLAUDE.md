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

**No test is accepted until it has been shown red.** Adopted 2026-08-22, after the
same defect reached nine instances across Tasks 2-7; a tenth arrived in Task 8 and
two more in Task 9, all written *after* the rule was adopted. Every one of them is
the same sentence — *the assertion does not depend on the code under test* — wearing
a different disguise:

- **the test supplies the value it checks** — Task 2's `.order_by()`, Task 3's
  `isinstance` on what `create()` returned, Task 5's `block1.position ==
  block2.position`;
- **the assertion is true of the framework regardless** — Task 6's
  `get_field("history")`, which raises on every model; Task 7's `"Questions"` and
  `"DA"`, both page chrome present with zero rows;
- **the setup silently never happened**, so the failure observed is a different
  failure — Task 7's inline prefixes, where deleting every `is_correct` key from the
  payload changed nothing;
- **the assertion sits inside the failure handler**, so it can only confirm a failure
  and never report one — Task 8's `except SystemExit: assert e.code == 1`, which
  passes whether or not a migration is missing. Both paths return normally: no
  exception means the function falls off the end, and an exception means the handler
  agrees the exit code was 1. Note the assertion is *also* the first disguise —
  `e.code` is `1` because Django's `sys.exit(1)` put it there two frames up.

- **the assertion names the leak in the wrong language** — Task 9's `assert
  "is_correct" not in body`. `is_correct` is a *Python attribute name*; a template
  that leaks it writes `{{ option.is_correct }}` and emits `True`, so the checked-for
  string can never appear however badly the page leaks.
- **the test verifies a weaker claim than the one it is named for** — Task 9's
  `test_preview_requires_staff` with an anonymous client. Anonymous is redirected by
  `login_required` too, so it passes against the decorator the task exists to reject.
  Only a **signed-in non-staff** user separates them.
- **the assertion reads the instance, not the row** — Task 6's
  `assert sitting.status == Status.PENDING` on what `create()` returned. Django applies
  `default=` in `Model.__init__`, in Python, before anything reaches Postgres, so that
  asserts *Django applied the field default* rather than anything about the stored row.
  Proved by giving `save()` a trailing `.update(status=SUBMITTED)`: the row said
  `SUBMITTED`, the assertion read `PENDING` off the stale instance, and every test
  passed. `refresh_from_db()` or a re-query closes it. This one matters beyond its own
  test — **F1's whole complaint is that legacy recomputed results instead of recording
  them, so every assertion here should be asking what the database holds.**

  **Three mechanisms now, and the third reached production.** Task 6's was a field
  default applied in `__init__`. Task 7's was a guard trusting the object it was
  handed, fixed with `select_for_update()`. Task 8's was `record_response` reading
  `item.sitting.status`: **Django caches a related object on the instance after the
  first access**, so a second call on the same `item` read a `Sitting` that still said
  `IN_PROGRESS` and a submitted sitting accepted a further response. Claude had
  explicitly said this one was safe — "the FK isn't cached on a plain `objects.get()`"
  — which is true of the first access only. Read `item.sitting_id`, which is a column
  already on the row and has no cached object behind it to go stale.
- **the test is never collected at all** — Task 7's F1 test, written as
  `def the_snapshot_survives_editing_the_question(...)` with the `test_` prefix
  dropped. This is the limiting case of the whole list: not a weak assertion but no
  assertion, because pytest's default `python_functions = test*` skips the function
  and the file still appears in the run contributing zero. Neither pytest nor ruff
  says anything. It hid behind an `ImportError` until the module existed, and would
  then have gone quiet inside a green suite. The defence is the one already in place —
  **a test that cannot run cannot go red**, so watching each new test fail catches it
  and reading the file does not.

Reading an assertion and judging it is what failed: nine of the first ten were caught
late, the prefix one survived **two** review rounds after the trap had been named
twice in the same session, and the tenth was read and passed twice by Claude. Breaking
the code and watching the test fail has never failed — `bisect_right - 1`,
`get_queryset` returning `.none()`, `if False:` on the option rule, and the whole of
Tasks 8 and 9. **Task 9 is the first task where every test was shown red before
acceptance**, and Task 6 of the exams plan was the second; both of Task 6's vacuous
assertions died on the first review round.

**To choose between two candidate assertions, find a mutant that lands in the gap
between them.** Task 6's `default → SUBMITTED` mutant killed the in-memory and the
refetched form equally, so it said nothing about which was stronger; only a mutation
making the instance and the row *disagree* separated them. A mutant both candidates
catch is not evidence that they are equivalent.

**Some tests have no mutant, and that is worth knowing rather than hunting** — see the
`mutation-sweep` skill for the two Task 6 examples and what to do about them.

**Prefer an assertion that states the property over one that forbids a symptom.**
Task 9's replacement gives two options identical visible content, differing only in
`is_correct`, and asserts the rendered list items are byte-identical. One assertion,
three leak mechanisms killed — a printed value, a conditional CSS class, conditional
markup — including forms neither of us enumerated. Pair it with a positive control
(`len(list_items) == 2`) so an empty page cannot pass.

**Assert the value, not that two values differ.** The exams plan's Task 9 grades one
percentage against two band sets and asserts each grade name as a literal. Asserting
merely that they differ catches a band set leaking across components — both grades
come out equal — but passes when the two sets are *swapped*, because two wrong answers
still differ. Verified 2026-09-17 against three leak mutants: the literals killed all
three, the inequality missed the swap.

So the rule is mechanical, not a matter of suspicion, because suspicion is
demonstrably not a reliable trigger:

- **He writes the test before the code where the plan says "write the failing
  tests"** — Task 7's step said exactly that and neither of us held it.
- **Claude mutates and reports** as part of the review round, not when something
  looks off. Name the line that must break to make this test fail, then break it.
- **Claude also writes the catalogue entries in `tools/mutation_sweep.py`** (agreed
  2026-09-06), and explains what each mutation does and which assertion kills it. It
  is review apparatus rather than implementation, and Claude has already run every
  mutation by the time the task ends — having Altus re-type them taught nothing and
  lost the reasoning behind each anchor.
- **A positive control earns its place when the setup step is the independent
  variable.** Task 7 produced three controls that no mutant could reach, because
  there the setup was *scenery* — other machinery already failed loudly if it were
  missing, a unique index or a rollback or a `get()` that raises. Task 8's
  `test_the_mark_uses_the_table_frozen_at_start_of_sitting` is the opposite: its whole
  claim is "this edit did not reach the mark", so an edit that never happened makes
  the claim vacuous and nothing else notices. Proved by breaking its filter to match
  no rows, at which point `marking-uses-live-table` survives again. The general test:
  ask whether the setup step is *enabling* the assertion or *is* the thing being
  asserted about.
- **Which query method a test reads through decides whether it needs one at all.**
  `objects.get()` raises on an empty result, so a test reading that way fails loudly
  when its setup produced nothing. `exists()`, `count()` and `filter()` are all
  *satisfied* by emptiness, and those are the ones that need a control beside them.
- **Before asking for an extra assertion, name the mutant it catches that the
  existing ones don't.** Three times in Task 7 Claude asked for a supplementary
  assertion that no mutant could reach: `items.count() == 1` after the freeze guard
  (pre-empted by `uq_one_item_position_per_sitting`, which refuses the second write
  first), `response == {}` beside `response is None` (a property of `JSONField`, not
  of this code), and `items.count() == 0` after the answer-key guard (pre-empted by
  `transaction.atomic()` rolling the writes back). This is the same rule already
  written down for choosing between two candidate assertions, applied to review
  instead of to test design — and it is the reviewer who keeps breaking it.
- **A test whose subject is a rendered page must be run with the row absent first.**
  Assert the string is missing, then assert it is present. Task 9 is templates, where
  every assertion is a substring of a page full of Django's own strings — the highest
  density this project will ever have for the second disguise.

**Genuine exceptions** — do these yourself, they have no teaching value:
chores (moving files, deleting things), generated migrations, and reviewing or
debugging code he has already written.

**One deliberate exception so far: Part A of the judge-records plan** (2026-09-25,
`172ec4a`…`7362203`). Altus asked to watch Claude do a stretch of work end to end and
chose that Claude write and commit all seven tasks, tests first, each shown red. It
was his decision, asked for explicitly, and it **does not change the default** — Part B
goes back to him writing. Read those commits as Claude's, which matters when judging
what he has and has not yet written himself: the eligibility rule, `awards.py` and
`enrol` are not code he typed.

**`CLAUDE.md`, the specs and the plans are yours to commit** (agreed 2026-08-08,
extended to plans 2026-08-10). Write and commit anything under
`docs/superpowers/{specs,plans}/` and this file directly — no need to hand the commit
back. **Every commit containing code or tests is his**, and that boundary is the
point: the documents are yours to maintain, the implementation is his to write.

## What this is

An online certification exam for SAGF rhythmic gymnastics judges. Real candidates,
real pass/fail decisions that must hold up if disputed. Being rebuilt from scratch
as of 2026-07-28.

Nothing is scheduled, so there is **no production pressure** — build in the right
order rather than racing a date.

**Two components, never combined, and separately enrolled** (confirmed 2026-08-08).
Theory and practical are independent results shown side by side. There is no average,
no weighting and no single pass/fail across the two. Legacy never combined them
either — that turns out to have been correct, not an omission.

**A candidate enrols for each independently**; sitting theory is not a prerequisite
for sitting the practical. Working assumption for the exams plan: that makes them
**two exams, not two components of one** —

```
Exam(level, year, kind=THEORY)     → 1 component,  N choice questions
Exam(level, year, kind=PRACTICAL)  → 4 components, 5 questions each
```

`Sitting: judge · exam` then stays exactly as the spec has it, enrolment is per exam,
and **F10 stops being possible rather than being guarded against** — a candidate who
did not sit the practical has no practical sitting, so there is no field for a
spurious zero to occupy. Modelling it as one exam with optional components means
every result must distinguish *not applicable* from *scored zero*, which is the
distinction legacy got wrong.

**Re-certification is a requirement** (confirmed 2026-08-13). A judge is examined
again each cycle and **both results must survive** — the earlier sitting is not
replaced by the later one. Legacy could not do this at all: `exam_result` declared
`UNIQUE (sagf_id)` with no year and no attempt number, so one row per person was the
schema's ceiling (**F11**). This is why `Exam` carries a year and why sittings
accumulate against a judge rather than a judge carrying a result.

*Theory* is multiple choice. **It is no longer a real certification component** — it
exists to exercise administering a multiple-choice paper across the different
question formats. `mark_choice` scores it and `score_component` over those marks
reproduces the legacy theory percentage exactly. Still worth building well, because
the questions app is what renders it, but it decides nothing.

*Practical* is the real exam. **Five routines, one per apparatus. The whole set is
shown four times, once per aspect** — every apparatus judged on `DA`, then all five
again on `DB`, then `AV`, then `EX`. Aspect-major, not video-major: the candidate
does not watch one routine four times in a row.

**Confirmed from data, 2026-08-15.** `rhytmic_master.db` stores the practical as
exactly four rows headed `Scoring D1 + D2`, `Scoring D3 + D4`, `Scoring AV` and
`Scoring EX`, five video filenames each, against a 20-row answer key of
`Rope, Hoop, Ball, Clubs, Ribbon` by four aspects. One row per aspect holding all
five apparatus **is** aspect-major. This ordering was derived from the domain before
the database was read; it is corroboration of a correct decision, not a finding —
the finding next to it is F14, which is about the missing join between those two
tables.

| aspect | was | grade bands |
|---|---|---|
| `DA` | D1+D2 | Difficulty |
| `DB` | D3+D4 | Difficulty |
| `AV` — artistry | AV | Artistry/Execution |
| `EX` — execution | EX | Artistry/Execution |

**Apparatus is a table, not a choice field** (decided 2026-08-08). The set is stable
— it changes only if FIG adds an apparatus — but per-apparatus reporting is a
requirement, so an official must be able to rename or reorder them without a deploy.
Note the domain distinction: **a gymnast competes on four apparatus, chosen by level;
a judge is examined on all five.** What a gymnast performs is not what a judge is
tested on, so the exam's apparatus set does not follow the competition's.

**The set and its order, for seed data:** `Rope, Hoop, Ball, Clubs, Ribbon` — FIG
competition order, and the order the legacy database used. This is `Apparatus.position`
1 through 5. It carries no exam content and is safe to commit as a fixture.

**Apparatus and aspect are independent dimensions — a 4 × 5 grid**, and results are
read *both* ways. Down a row gives the aspect's component score, which is what
grades into a category. Across a column gives the candidate's marks for one
apparatus, which is what they actually want to see, exactly as a competition score
sheet works. **Apparatus is therefore a real field, never implied by position in a
list** — ordering is the thing that drifts.

Each score is entered against a timer; when it expires the candidate is moved on and
cannot go back.

Use the **current** FIG naming — `DA`, `DB`, `AV`, `EX` — not the old `D1+D2` /
`D3+D4` labels the legacy answer key carries (decided 2026-08-08).

So a candidate gives **20 marks**, each compared against that cell's own expert score
with `mark_numeric`. **That is where F5's magic number came from**: legacy summed 20
marks worth 5 each and called the total a percentage, which was only ever correct
because 5 apparatus × 4 aspects = exactly 20. Nothing in the code recorded that
dependency; a sixth apparatus would have scored everyone out of 125 while still
printing "%".

**Decided 2026-08-10: theory and practical are separate models.** The practical asks
nothing about the routine — the candidate watches and enters a number — so a practical
item has no stem blocks and no options, only a routine, an aspect and an expert score.
It shares nothing with a theory question but a position in a component. The spec's
original single `Question` with `marking_scheme: CHOICE | NUMERIC` has been revised;
the collapse-into-one-shape argument holds for the five theory *layouts*, not across
theory and practical. See the spec's Questions section.

**Decided 2026-08-08: a routine exists once and the four items reference it.**
The apparatus and its video belong to the routine; the aspect and the expert score
belong to the question. Four question rows each owning a copy of the same video is
the papers argument again — replace a video, miss one of the four copies, and a
candidate judges `EX` against last year's routine with no error anywhere. It also
matches the domain: a judge watches **one routine** and makes four judgements about
it. Note this is a **deviation from the spec**, which has `Question → QuestionBlock`
holding media and nothing in between; the exact shape is for the questions-app plan.

The four aspects stay **separate** — `DA` and `DB` are not averaged into one
Difficulty score. Each is `score_component` over its five videos, then `grade`
against the band set for its type. Note the two band sets differ: Excellent is 80%
for Difficulty but 90% for Artistry/Execution, which `grade(percentage, bands)`
already supports because bands are an argument.

**Decided 2026-08-08: `Difficulty = mean(DA, DB)` for the category rule, and it is
the mean of the two *rounded* aspect scores.** `DA` and `DB` stay separate for
scoring and reporting — a candidate sees both — but the category rule takes three
values, Difficulty, Artistry and Execution, which is why the spec's two worked
examples name Difficulty once.

**The rounding order is not cosmetic.** Rounding each aspect and then averaging is
not the same as averaging the raw values and rounding once: over a window 0.1 wide
on each axis there are 2,750 disagreements, and **1,020 of them change the Difficulty
grade** against the 80% floor. For example `DA 79.900`, `DB 80.085` gives `80.00`
Excellent one way and `79.99` Very Good the other — same twenty marks, different
category.

Take the mean of the rounded scores, for the same reason `grade` consumes a rounded
percentage: the candidate is shown `79.90` and `80.09`, and averaging those by hand
must reproduce the result. A number that cannot be recomputed from the figures on
the certificate is the one that loses an appeal.

**The examination produces a category, but does not award one** (established
2026-08-10 from General Judges' Rules §2.6; SAGF follows FIG). The awarded category
is capped afterwards by judging experience, by a first-cycle maximum of Category 3,
and by a limit of dropping at most two categories per cycle. **This system computes
the examination result and stops there.** That is the concrete reason the spec keeps
scoring and certification as separate events recorded against different people — the
information that caps the award is history the exam has never seen.

**The four grades then determine one overall category, and that piece is not built.**
`score_component` and `grade` get you to four grades; nothing turns four grades into
a category. From the two examples in the spec — Category 1 needs Difficulty
excellent with Artistry and Execution very good, Category 4 needs all at pass — the
rule looks like *the highest category whose per-aspect minimum grades are all met*,
which is the same lower-bound shape as `GradeBand.minimum` and the F9 level rule. The
weakest aspect caps the category. **The exact requirements per category are still
unknown** — see Open questions.

**Theory questions are banded by level, cumulatively.** A level 2 candidate sits
every level 1 question plus the level 2 additions; level 3 sits all three bands, and
so on. So a question carries the *lowest* level obliged to answer it, and selection
is `question.minimum_level <= candidate.level` — a lower-bound comparison, the same
shape as `GradeBand.minimum` and `floor_band_index`. Modelling it as
`question.level == candidate.level` looks reasonable and silently hands a level 3
candidate only the level 3 additions, sitting them a fraction of their exam. That is
exactly what the old app did — see **F9**.

**Decided 2026-08-05: a question exists once, and something else lists which
questions it contains.** Membership is explicit data — a many-to-many, not a scalar
`level` column and not a `minimum_level <= candidate.level` query. Overlap between
levels is the same question row referenced twice, never a copy of it.

Two things this buys, and both were argued rather than assumed. Duplicating a
question per level means an answer-key correction has to find every copy, and a
missed copy leaves two cohorts marked against different keys with no error anywhere
— F1's family. And a pure cumulative rule cannot express a level that *drops* or
replaces an inherited question; the first time the syllabus does that you bolt on an
exceptions table and arrive at the join table by a worse road.

"Cumulative" therefore describes how a question set is **built** — seed level 2 from
level 1, then add — not how it is queried. Note the usual reason to duplicate does
not apply here: keeping historical question sets stable is F1's snapshot's job, so
duplication buys nothing there.

**Refined 2026-08-08: the owner is `ExamComponent`. There is no separate `Paper`
model.** The spec already defines `ExamComponent` as "one per marked section of the
exam", carrying its own grade bands and its own marking table — which is exactly the
thing that should own a set of questions. Theory is one component holding choice
questions; the practical is four components holding five numeric questions each. A
level 2 theory component references the same question rows as level 1's, plus its
own additions. **One mechanism for both halves of the exam**, rather than papers for
theory and components for the practical.

The consequence for planning: **the questions app is content only** — `Question`,
`Routine`, `Apparatus`, blocks, media, admin, preview. Membership and selection live
with `ExamComponent` in the exams app, and **F9 moves to the exams/sittings plan
with them**, because F9 is about which questions a candidate is given, not about what
a question is.

**Absence is not a value — and the two-exam split is what enforces it.** Legacy
fabricated a practical answer of `"0"` for candidates who sat no practical, so a
component they never attempted scored roughly zero and was indistinguishable from
failing it (**F10**). With theory and practical as separate exams and separate
sittings, a candidate who did not sit the practical has no practical sitting at all,
and there is no field for a spurious zero to occupy.

Keep the principle anyway, because it recurs: this is the same distinction
`to_decimal` draws between a blank answer and an unreadable one (F3), and
`score_component([])` raising rather than returning `0` is the same guard inside the
scoring package. Any future code that aggregates across components must treat
absence as absence, never as a number.

## Read these before doing anything

- `docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md` — the design.
  Includes fifteen numbered findings (F1–F15) from the old app; each one is a bug the
  rebuild must fix, and several have tests written specifically to pin them. F1–F8
  came from the original audit; **F9 and F10 were found on 2026-08-05** while
  checking how legacy selected questions by level; **F11 and F12 on 2026-08-13** and
  **F13–F15 on 2026-08-15**, from old working databases rather than from the code.
  Assume there are more.
- `docs/superpowers/plans/2026-07-28-scoring-package.md` — the current plan.

## Layout

`docs/superpowers/{specs,plans}/` holds the specs and plans. `rhythmic/` is the new
system, and **paths in the plans are relative to it**. `legacy/flask_backend/` is the
2023 Flask app — **reference only, do not modify or run it**.

**Tests live in `rhythmic/tests/`, one subdirectory per package** — `tests/scoring/`,
`tests/questions/`, `tests/exams/`, `tests/config/`. Reorganised 2026-08-25 from a flat
`tests/` whose filenames carried the app as a prefix; the prefixes are gone, so it is
`tests/questions/test_theory.py`, not `tests/test_questions_theory.py`.

**Claude proposed putting each `tests/` inside its app instead, and that was wrong** —
`.vscode/settings.json` runs pytest with `cwd` = `rhythmic` and `pytestArgs: ["tests"]`,
so deleting `rhythmic/tests/` silently breaks VSCode's test discovery while the CLI
suite still passes. Check that file before moving tests again.

**`tests/` and every subdirectory need an `__init__.py`.** Two different failures
otherwise, both reproduced in this tree rather than recalled:

- **No `__init__.py` anywhere:** pytest's default `prepend` import mode names a module
  by its bare filename, so `tests/scoring/test_smoke.py` and `tests/config/test_smoke.py`
  collide — `import file mismatch`, which aborts collection rather than failing a test.
- **Subdirectories marked but `tests/` not:** worse and less obvious. pytest inserts the
  first unmarked ancestor on `sys.path`, so the module becomes `questions.test_theory`
  and `questions` resolves to **the real app package**. Result:
  `ModuleNotFoundError: No module named 'questions.test_theory'` on eight files at once.
  The test directory name shadowing the package it tests is the trap here.

**`tests/scoring/ruff.toml` re-applies the framework ban to scoring's own tests.**
Ruff resolves the nearest config per file, so `tests/scoring/` cannot inherit
`scoring/ruff.toml` — different subtree. Without that file, a scoring test could
`import django` and nothing would object, which is a hole in exactly the boundary
`scoring/` exists to hold. **Keep the two banned-api lists identical.** The Django test
directories deliberately do not get it — verified with `ruff check --no-cache` in both
places, and note ruff's cache will happily report a stale pass right after you add a
config, so use `--no-cache` when checking that one.

**One pytest config, and it is `pytest.ini` at the repository root** (2026-08-25).
`rhythmic/pyproject.toml` no longer carries `[tool.pytest.ini_options]`; putting it back
re-creates the split described below. Only a config at the root can see `legacy/` in
order to exclude it, which is why the root won.

- **pytest resolves its config by walking UP from the common ancestor of the arguments
  and stopping at the first match** — the opposite of ruff, which resolves the *nearest*
  config per file. While both files existed, a run from `rhythmic/` stopped at
  `pyproject.toml` and a run from the root used `pytest.ini`, so the two agreed only by
  luck. Verified after the change: root, `rhythmic/`, VSCode's invocation and a
  single-file run all report `configfile: pytest.ini`.
- **`norecursedirs` replaces pytest's defaults, it does not extend them.** The stock list
  is therefore repeated in the file alongside `legacy`. It is load-bearing: with `legacy`
  removed, `pytest .` from the root aborts collection with
  `ModuleNotFoundError: No module named 'flask'`, because the venv no longer has Flask.
- **`testpaths` is ignored the moment an argument is passed**, so it is a convenience for
  bare runs and never a safety boundary. `norecursedirs` is the boundary.

The `git add` lines in the two finished plans still name the old flat paths. Leave them —
they record commits that were actually made, like the pre-convention commit messages.

`legacy/` is kept for exactly two things: the exam media (117 images, 10 videos)
and the type 1–5 templates to check new rendering against. **It gets deleted when
the media is migrated and the block renderers are built** — that condition was
agreed, so don't let tidiness pull the trigger early, and don't propose building on
it either.

The FastAPI backend was deleted on 2026-07-28 (recoverable from `4e6aa1b`,
`206ff42`). Don't suggest reviving it.

**Two old working SQLite databases, both untracked and covered by `.gitignore`'s
`*.db`. They hold the real question bank and the practical answer key, so neither may
ever be committed and their contents must not be quoted into commits, plans or chat.**
Aggregate shape — counts, distributions, column types, JSON key names — is safe, and is
where F9's confirmation and F11–F15 came from.

- **`rhytmic.db`**, produced 2026-08-13. 75 questions, all `question_type = 1`, none
  referencing media. A later, reduced state. Source of F11 and F12.
- **`rhytmic_master.db`**, found 2026-08-15. **The original bank: 89 questions across
  all five types, 85 theory and 4 practical.** Source of F13–F15. Predates the change
  that introduced levels, so it says nothing about F9.

**They are evidence of what was done, not a model for what to do.** Every structural
choice in them is one the rebuild is deliberately reversing: scalar `exam_level`,
positional `answer_1..answer_20` keys, `TEXT` expert scores, one result per person,
five private JSON schemas inside `VARCHAR` columns. Read them to find out what went
wrong, never to copy a shape.

**Two corrections the master database forced, both of which had reached this file as
fact.** The type 2–5 layouts were recorded as having no known data; they have data —
1 type 2, 2 type 3, 5 type 4, 39 type 5 — and their shapes are in F13. And the tracked
media in `legacy/` was recorded as unreferenced; the master database references 98
distinct files (88 `.jpg`, 10 `.mp4`) and **all 98 are present on disk**, across 44 of
the 89 questions. So the media migration has a manifest, and the images are provably
exam content rather than merely suspected of it — which raises, not lowers, the
priority of the exposure noted under Hard constraints.

Both corrections came from a claim in this file being checked rather than trusted.
Treat the rest of this section the same way.

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
- **When handing him a commit, say what the body should carry *before* giving the
  command, and give bare `git commit` rather than `git commit -m`.** `-m` commits on
  the spot, so body guidance that follows it arrives after the commit exists and
  costs a rebase — this happened on 2026-08-10. Reserve `-m` for commits that need no
  body at all, such as a pure formatting chore.
- **Cite the finding** when a commit fixes one: `fix(scoring): compare answers as
  Decimal, not string (F3)`. The findings are the spine of the rebuild and the log
  should be searchable by them.

No release automation is wired up and none is planned; the prefixes are for humans
reading the log. There is no `commit-msg` hook — **this convention is held by
discipline alone.** The `pre-commit` hook added on 2026-08-04 enforces ruff, and
says nothing whatever about commit messages; don't mistake one for the other.

## Current state

**Four plans finished: the scoring package (seven tasks), the Django skeleton
(five), the questions app (nine) and exams-and-sittings (ten, closed 2026-09-25 at
`b8d7b6b`).** As of 2026-09-25 the suite passes — 216 tests and both
`ruff check .` and `ruff format --check .` are clean. Run all three from `rhythmic/`.

**Postgres must be running for the full suite to pass.** `docker compose up -d` from
the repository root. `test_django_smoke.py::test_database_is_reachable` needs it, and
so does every `@pytest.mark.django_db` test in the questions app; the scoring tests
do not.

**Don't chase a plan's own test-count estimates** — the questions-app plan predicted
54 by Task 6 and was written before the tests were.

**The exams-and-sittings plan is written** —
`docs/superpowers/plans/2026-08-24-exams-and-sittings.md`, ten tasks in two parts. Part A
is the exam definition (`Exam`, `ExamComponent`, marking tables and grade bands as rows,
explicit membership) and is independently shippable; Part B is the sitting, the freeze and
marking. **Six findings close in it** — F1 and F2 at the freeze, F3 and F4 at marking, F5 at
the component percentage, F9 at membership, F10/F11/F12 at the two-exam split and the
dated exam.

**Part A is finished — Tasks 1 to 5 landed.** `Exam` carries level, year and kind;
`ExamComponent` is one per marked section; `MarkingTableRow` and `GradeBandRow` hold
the tables as rows, with `exams/tables.py`
adapting them into `scoring/`'s frozen dataclasses; `ComponentQuestion` and
`ComponentPracticalItem` make membership explicit rows.

**Part B has started — Task 6 landed, `e33870b`.** `Sitting` is judge · exam with a
status defaulting to `PENDING`, nullable `started_at`/`submitted_at`/`certified_at`,
a `certified_by` pointing at the official rather than the candidate, and
`HistoricalRecords`.

**Task 7 landed, `7f1f824`.** `SittingItem` holds one foreign key, to its sitting;
the component's name, position and marking scheme are **copied strings**, and the
question is copied into `question_snapshot` with the answer in a separate
`marking_key`. `exams/freeze.py`'s `start_sitting` walks the components in order,
writes one item per member with a running position, and re-reads the sitting through
`select_for_update()` inside the transaction rather than trusting the instance it was
handed. The freeze costs **13 queries whether the paper has 1 member or 200** — it
was 385 before the prefetches, and `test_starting_a_sitting_does_not_issue_a_query_per_member`
pins it.

**Task 8 landed, `0dedf18`, and F3 and F4 close with it.** `exams/marking.py` holds
`record_response` and `submit_sitting`; marks are written once at submission and
nothing recomputes them.

**Task 9 landed, `1722971`, and F5 closes with it.** `ComponentResult` stores one
percentage and one grade per component, written once at submission. `score_component`
takes the mean of per-item percentages, so legacy's magic 20 has nowhere to hide. Two
mutants pin it: the bare sum, and a divisor hard-coded to the item count — the second
is invisible at five items, which is why the F5 test insists on six and asserts the
item count before anything else.

**Task 10 landed, `b8d7b6b`, and closes the plan.** The definition models are edited
through the admin with inlines, including the practical membership inline the plan
was missing until 2026-09-19. `Sitting`, `SittingItem` and `ComponentResult` are
records: all three return `False` from `has_add_permission`, `has_change_permission`
and `has_delete_permission`. **Permissions, not `readonly_fields`** — view-only mode
covers a field added later, and an allow-list had already gone stale twice.

**`Sitting` is locked down entirely** (decided 2026-09-25). The plan had given it a
plain `SimpleHistoryAdmin`, which inherits every permission, so an official could set a
`SUBMITTED` sitting back to `IN_PROGRESS` and `record_response` would accept answers
into a paper already marked. The cost is that `certified_by`/`certified_at`/`outcome`
cannot be set in the admin either — **certification belongs to the accounts plan as its
own action**, not to a change form that also exposes `status`.

**The review mutants found four guards no test reached** — add on all three models and
delete on `Sitting` — plus the exam page's component inline. Every one was written
correctly and none was executed: the guard-clause lesson from Task 9 again, at the
admin layer. Deleting a `Sitting` was the worst, since both FKs into it `CASCADE`. An
add guard is pinned by a GET returning 403, which is sufficient there because
`add_view` refuses before any form exists; a change guard is pinned only by the
reloaded row, because a change POST can 302 without saving.

**Findings closed by this plan:** F1 and F2 at the freeze
(`test_the_mark_uses_the_table_frozen_at_start_of_sitting`,
`test_the_grade_uses_the_bands_frozen_at_start_of_sitting`), F3 and F4 at marking, F5
at the component percentage, F9 by absence of any level comparison, and F10/F11/F12 by
the two-exam split and the dated exam.

**Next action: Part B of the judge-records plan**,
`docs/superpowers/plans/2026-09-25-judge-records.md`, Task 8 — `Certification` and its
constraints. Part A (Tasks 1–7) landed 2026-09-25, written by Claude at Altus's request
(see "One deliberate exception" above): `JudgeProfile` and `RosterEntry` in `accounts`;
`Cycle` and `CategoryRequirement` as rows; the pure eligibility rule and `enrol`, with a
random `candidate_number` and a recorded override; the component aspect frozen onto items
and results; and `exams/awards.py`, the §2.6 examination category and the award bounds.
Plan 2 (sign-in) follows, then the React island last.

**A data assertion on an admin POST goes vacuous when the model gains a required
field** (2026-09-25). `test_a_sitting_cannot_be_changed_through_the_admin` asserted only
that the row was unchanged. Task 4 added a required `candidate_number` the payload
lacked, so with the lock removed the form failed validation, re-rendered with 200, and
left the row unchanged anyway — green against an editable admin, found only by the full
sweep. It now also asserts **403**, the one response only the permission produces.
"Assert the data, not the status" still holds for a 302, which can save; it was never a
reason to ignore the one status that cannot be faked.

**Two things Part A found that the plan did not.** `test_roster_levels_round_trip` was
dropped: it asserted that a Postgres array keeps its order, which no mutant of this code
can break. And `enrol` needed two tests the plan omitted — the open-sitting check and
the submitted-sitting retake — because the pure rule's tests exercise the boolean, never
the query that computes it.

**Grade bands are frozen onto the item as well** (decided 2026-09-13). Grading needs
bands, `SittingItem` holds no component to ask, and a lookup by frozen
`component_name` is F2's shape — so they ride on the item like the marking table, at
180 bytes a set. `submit_sitting` is a pure function of the rows it reads. Only
`test_the_grade_uses_the_bands_frozen_at_start_of_sitting` pins that:
`results-uses-live-bands` survived all 196 other tests, because every other test edits
bands *after* submission, when live and frozen still agree.

**The freeze refuses a component with no grade bands, and that guard shipped raising
`NameError`** — renamed at its class but not at its `raise` — under 192 green tests.
**A guard clause is the production code a suite is least likely to execute**, because
the fixtures that make every other test pass are exactly what stop it firing. Its own
test is what found it, and `grade-band-guard-wrong-name` keeps it found.

**F3 cannot fail quietly here, and that is a property of `Decimal` rather than of a
test.** `Decimal` refuses `float` operands, so a float reaching a mark raises
`TypeError` instead of shifting a band — the review-gate mutant dies on a type error,
not a wrong number. **F4 does not close itself inside `scoring`:** `to_decimal` raises
`UnparseableAnswer` and `mark_numeric` does not catch it, so the exception escapes —
which is the legacy crash. `submit_sitting` catches it and stores `0`, and the `try`
wraps only the `mark_numeric` call: widen it two lines and a corrupt frozen marking
table scores every candidate nought, which is F10's shape.

**The marking table is frozen into the item** (decided 2026-09-08, measured before
deciding — 41 KB of duplication per practical sitting, about 2 MB per fifty). That
makes `submit_sitting` a pure function of the row it marks, with no lookup and no key,
and it closes the window *between* freezing and submitting that the plan's own test
never reached. Only `test_the_mark_uses_the_table_frozen_at_start_of_sitting` has
teeth for it: a live-lookup implementation survived every other test in the suite,
because they all edit the table after submission when live and frozen still agree.

**F1 needs three tests and only one of them has teeth, which was not obvious.** The
claim splits into *what* was copied, *when* it was used, and *whether* it was recorded.
Task 7's snapshot test covers the first. Task 8's
`test_marks_are_not_recomputed_after_submission` was billed by the plan as "the F1 test
with teeth" and is not — like Task 7's, it edits upstream *after* submission, when a
stored column could not move anyway; both are standing guards against a future read
path that recomputes. The one that bites is
`test_the_mark_uses_the_table_frozen_at_start_of_sitting`, which edits *between* the
freeze and the submission: `marking-uses-live-table` survives the entire suite without
it. `freeze-reuses-live-question` stays out of the catalogue — there is still no read
path for it to break.

**F9 is closed, and closed by absence.** There is no level field on a membership row and no
comparison to a candidate's level anywhere — selection is "the component's members", so
legacy's `exam_level == user.level` has nothing to be written against. F10, F11 and F12
went with the two-exam split and the dated exam. What remains for Part B is F1 and F2 at
the freeze, F3 and F4 at marking, and F5 at the component percentage.

**F10 and F11 now have tests as well as a design.** A pending sitting *is* the
enrolment, so a candidate who did not sit the practical has no practical sitting and
legacy's fabricated `"0"` has no field to occupy. Nothing constrains `(judge)` or
`(judge, exam)`, which is what lets a judge accumulate sittings and retake — the two
migration mutants `unique-judge-sitting` and `unique-judge-exam-sitting` are what pin
that absence, since a diff cannot show a constraint that was never written.

**Still unguarded, and worth knowing before Part B.** `Exam.kind` and `ExamComponent.aspect`
are unconnected: a `THEORY` exam with a `DA` component is representable and nothing objects,
because a Postgres `CHECK` cannot reach across tables. `ExamComponent.marking_scheme` and
`difference_steps` *are* paired, by `ck_component_steps_match_marking_scheme` — the first
constraint in this app spanning two fields. And `level`/`year` accept `0`, since
`PositiveSmallIntegerField` only bounds them below.

**`exams/tables.py` is the only module in the tree importing both `scoring` and Django**,
and that is a property to preserve rather than a coincidence. `scoring/ruff.toml` bans the
frameworks inside `scoring/`; nothing bans `scoring` from the Django side, so the boundary
in that direction is held by keeping the join in one file where a reviewer can see it.

**`rhythmic/tools/mutation_sweep.py` exists and should be run at the end of every
task from now on.** It breaks one claim at a time and checks that a test objects; a
SURVIVED mutant is a change to the code nobody noticed. Run from `rhythmic/`:

```bash
../.venv/bin/python tools/mutation_sweep.py
```

Latest run, 2026-09-25, after Part A of the judge-records plan: **121 mutants, 121
killed, 0 survived** in 9m44s — after the drift-test and bytecode fixes, both in the
`mutation-sweep` skill. The run before it, after Task 10 and the `list_filter` test, was
**77 mutants, 77
killed, 0 survived** — the first clean sweep since that mutant entered the catalogue.
Treat any SURVIVED line as a stop from now on; there is no standing exception left to
skim past. The thirteen `exams/admin.py` mutants' nine permission flips anchor on each
class's comment line, because the guard methods are identical and the sweep replaces
only the first match; reword a comment and its mutants report `UNAPPLIED`.

**`list_filter` survived twelve runs because the obvious test cannot kill it.** The
admin's `lookup_allowed` accepts a lookup on any local field, so `?aspect=DB` filters
the changelist with or without `list_filter` — measured, 1 row of 4 both ways. What the
line adds is the sidebar, whose links read `?aspect__exact=DA`; the test asserts that
string. Assert on what the code adds, not on the framework behaviour beside it. The
run was 266s after Task 10, up from 205s — the thirteen admin mutants at 4-6s each.
**How the sweep scopes its tests, which mutants
need `--create-db`, where a claim actually lives and what `UNAPPLIED` means are in the
`mutation-sweep` skill.**

**The sweep runs the likely killer first** (`142bf81`). Cheapest-file-first was
optimising the wrong thing: under `-x` a mutant costs the distance to the test that
objects, not the price of the files ahead of it, and the admin mutants were each
running 46 tests that cannot fail before reaching the twelve that can. `batches_for`
guesses a test file from the mutated module's name, falls back to the app scope, and
finally to everything still unrun — correctness in the fallback, speed in the guess.
137s to 99s, verdicts unchanged.

**The survivor re-run was not actually running everything, and Task 6 caught it**
(fixed `e33870b`; the mechanism is in the `mutation-sweep` skill).

**Three near-misses in Task 4, all the same shape: the test's inputs matched what the
mutation would produce, so the assertion could not see it.**

- Rows inserted in *ascending* `expert_minimum` passed with `Meta.ordering` deleted — for a
  small unordered scan Postgres returns insertion order, which already matched. Inserting
  them descending is what makes the mutant die, at `scoring/types.py:40`.
- A `lookup` on the **middle** column of three survived a mutation reversing the
  percentages: index 1 is a fixed point of a 3-element reversal. Any other column kills it.
- A test named for grade bands asserted on marking-table lookups instead, so
  `build_grade_bands` could `return []` with the whole suite green.

The defence is mechanical: **make the test's inputs disagree with the order or shape the
mutation produces**, and pair a behavioural assertion through the public entry point with a
structural one on what was built. The structural assertion — comparing a whole row against
a tuple literal — killed both the reversal and a `list`-instead-of-`tuple` mutation that has
no behavioural symptom at all.

**The three finished plans' commit-by-commit history lives in**
`docs/superpowers/decisions-log.md` — the scoring package (`c0839c5`…`c54d8c5`), the
Django skeleton (`13262c1`…`37500f1`) and the questions app (`d035ce8`…`797b09f`).
Read it before touching `scoring/`, `config/`, `questions/`, `compose.yaml` or the
`.env` handling. It is where the derived findings live: why `MarkingTable.lookup` is
keyword-only, why `grade` consumes a rounded value, why `Routine.Meta.ordering` needs
a `pk` tiebreak, why deferred constraints are invisible to `pytest-django`, and why a
missing name in a Django template renders as nothing at all.

**Authoring an option in the admin takes five saves**, and the three fix routes are
known — see `rhythmic/questions/CLAUDE.md`, which loads when you work in that app.

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
- **It checks the staged blob, not the working-tree file** (fixed 2026-08-10). It
  reads each file with `git show ":path"` and pipes it to ruff with
  `--stdin-filename`, so what is checked is exactly what is committed, and per-file
  config resolution still applies — `scoring/` still gets its framework ban.

  It did check working-tree files until 2026-08-10, and that let a real defect
  through: `git add` a dirty file, `ruff format` the working tree, `git commit`, and
  the hook sees a clean tree while git commits the dirty blob. That is how the
  whitespace in `37500f1` was committed. `git stash --keep-index` would also have
  fixed it and was rejected — a hook that stashes can lose work if it exits badly.

  **Consequence when it blocks you: re-stage.** Fixing the file on disk changes
  nothing until `git add` puts the fix in the index.

## Open questions, none blocking

1. **Partly resolved 2026-08-08.** Naming follows the **current** cycle — `DA`,
   `DB`, `AV`, `EX` — not the legacy answer key's `D1+D2` / `D3+D4`. What is still
   open is the *table data*: which marking table and which band boundaries SAGF
   actually publishes. Affects data loaded at runtime, not the design.
2. Candidates per sitting. Assumed tens.
3. **Resolved 2026-08-05.** `mark_choice` is an SAGF national addition, not a FIG
   one. **Superseded 2026-08-08:** theory is no longer a real certification
   component at all — see What this is.
4. **Resolved 2026-08-08.** Theory and practical are never combined. Two separate
   results. Legacy's `main/routes.py:453-460` carried them side by side with no
   average or combined grade anywhere, which was right.
5. **Resolved 2026-08-10.** The table is **§2.6 of the General Judges' Rules**, not
   table 2.4 of the RG-specific ones, and **SAGF follows FIG**. Full table and the
   experience caps are in the spec. The inferred rule held: highest category whose
   three minimums are all met, weakest aspect capping. Note Category 1 is the only
   asymmetric row, and that **the examination result is an upper bound on the award,
   not the award itself** — judging experience, a first-cycle cap and a two-category
   drop limit all apply afterwards.
6. **Resolved 2026-08-08.** "Difficulty" in the category rule is `mean(DA, DB)` —
   the mean of the two rounded aspect scores — not a requirement that both reach the
   grade independently. See What this is for the rounding-order argument.
