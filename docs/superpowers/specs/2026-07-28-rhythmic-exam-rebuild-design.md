# Rhytmic Exam — Ground-Up Rebuild

**Date:** 2026-07-28
**Status:** Design agreed, pending implementation plan

## Purpose

Rebuild the SAGF rhythmic gymnastics judge certification exam system. Real candidates
depend on the result, and the rebuild doubles as a deliberate learning exercise for the
author, who writes all implementation code.

Two prior implementations exist. Both are reference material only:

- `legacy/flask_backend/` — the working 2023 monolith. Source of truth for domain behaviour.
- `fastapi_backend/` — an incomplete 2026 API port with no frontend. Deleted 2026-07-28;
  recoverable from commits `4e6aa1b` and `206ff42`.

Neither is a foundation. Mine them for domain rules, then replace.

## Why rebuild

Four problems, all confirmed against the existing code:

1. **The content model is rigid.** `ExamQuestions.option_a..option_d` are `String(256)`,
   so any layout that isn't four short strings smuggles a JSON document into a varchar and
   declares itself a new `question_type`. Five types today, each with a bespoke unpacking
   function in `exam_utils.py` and a bespoke branch in `theory_exam.html`.
2. **Results are not defensible.** See "Findings" below.
3. **Delivery is dated.** Jinja plus Bootstrap 3; the FastAPI port has no UI at all.
4. **Operations are manual.** Users are approved one at a time by an admin; questions are
   imported by CSV; images are referenced by path convention.

## Findings from the existing system

These drive the design and are recorded because each one must be fixed.

### F1 — Results are recomputed, not recorded

`main/routes.py:428` loads correct answers from the *live* `ExamQuestions` table and scores
stored answers against them at display time. Editing a question's answer key silently
rewrites every historical result. A candidate who passed can become a candidate who failed
with no record that anything changed.

### F2 — Latent key mismatch between answers and answer key

The theory form names each radio `q['q']`, set from `question.id` (primary key) in
`make_type_one_question`. `results()` builds the answer key from `question_id` — a
different column. They coincide today only because both were populated sequentially.
Diverge them and `user_answers.get(k, "E")` misses every lookup and every candidate scores
zero, silently. `calculate_theory_score` cannot distinguish "answered wrongly" from "was
never asked".

### F3 — A correct practical answer can score zero

`get_practical_mark("0.30", "0.3")` returns **0**. String equality fails, the numeric path
computes a difference of `0.0`, and the guard `if difference >= 1 or difference <= 0`
returns no marks. `_sanatize_user_answer` normalises `,`, `/` and a leading `.`, but never
trailing zeros. Verified by execution.

### F4 — An off-grid practical answer crashes the request

`get_practical_mark("0.30", "0.23")` raises `ValueError: 0.07 is not in list`, because
`diff_arr.index(difference)` requires an exact match on a 0.05 grid. A 500 error mid-exam.
Verified by execution.

### F5 — The practical percentage is not a percentage

`exam_utils.py:170`: `percentage = _round_half((total_score/100) * 100)` is the identity
function. The reported "percentage" is the raw mark total, correct only because there are
exactly 20 answers worth 5 marks each. A fifth practical question silently scores everyone
out of 125 while still reporting "%".

### F6 — Scoring has no tests

`test/unit/` contains tests for `db_import_export`, exam date utilities and models. There
is no test file for `exam_utils.py`. The code that decides whether a judge is certified is
the only part of the system with zero tests. Note that `get_practical_mark` was already a
pure function — purity made testing possible but did not make it happen.

### F7 — `download_results` is unauthenticated

`main/routes.py:474` has neither `@login_required` nor `@admin_required`, unlike every
other results route. It exposes all candidates' names, SAGF IDs and scores.

### F8 — Question editing renders unescaped HTML

`edit_exam_question` stores raw HTML from the admin form and templates render it with
`|safe`. Acknowledged in a code comment at `main/routes.py:146`.

### F9 — Cumulative question levels are selected by equality

`main/routes.py:450` and `:497` filter theory questions with `exam_level == user.level`,
and `ExamQuestions.exam_level` is a single scalar column, so a question belongs to exactly
one level. The rule is cumulative — a level 2 candidate sits level 1's questions *plus*
level 2's. As written they sit only level 2's, and `calculate_theory_score` divides by the
filtered count, so the reported percentage looks entirely normal. A judge is certified
without ever being asked the level 1 material. Selection is a lower-bound test, not an
equality.

The question bank was removed from this repository on 2026-07-28, so whether the data
worked around this — by importing level 1's questions a second time under `exam_level =
"2"` — could not be checked at the time. **Settled 2026-08-13 against an old working
database:** it did not. Level 1 holds 50 questions and level 2 holds 25, with `question_id`
ranges 1–50 and 51–75 and **no overlapping question text at all**. A level 2 candidate was
therefore asked 25 questions rather than 75 — the additions only, never the foundation.

Two things follow. The cumulative rule existed nowhere: not in the query, and not as
duplicated rows in the data either. And `user.level` is a nullable `VARCHAR` that was blank
for 16 of 22 users, so for most of the roster the equality test had nothing to compare.

### F10 — A component the candidate never sat is scored as zero

`main/routes.py:457`: `if not result.practical_answer: result.practical_answer =
'{"answer_1":"0"}'`. Some levels sit no practical component at all. Rather than recording
the component as absent, the view fabricates an answer, which then marks against every
practical question and reports roughly 0%. The result is indistinguishable from a candidate
who sat the practical and failed it — on a straight average of two components, a
theory-only candidate scoring 90% is reported at 45%.

Distinct from F5, which concerns the arithmetic of the practical percentage. This is a
component that should not exist for that candidate having a score at all. The same
conflation F3 makes between a blank answer and an unreadable one: absence is not a value.
Found 2026-08-05, after the original audit.

### F11 — A candidate can hold only one exam result, ever

`exam_result` declares `UNIQUE (sagf_id)` and carries no year, cycle or attempt number. One
row per person is all the schema can hold, so a second examination has nowhere to go: it
overwrites the first or it is refused. There is no third option.

**Judges recertify every cycle**, so this is not an edge case — it is the normal life of
every record in the table. A judge examined in two consecutive cycles has one row, and
whichever attempt it holds, the other is gone. Nothing in the schema records that a
previous examination happened, which also means the history that caps an awarded category
(see the judging-experience rules) can never be reconstructed from this system's own data.

The rebuild's `Exam(level, year, kind)` and `Sitting: judge · exam` make re-sitting the
ordinary case rather than a schema violation: a judge accumulates sittings, each against a
dated exam, and the record of the earlier one survives the later one. **Re-certification is
a requirement, confirmed 2026-08-13**, not a nice-to-have inherited from the old shape.

Found 2026-08-13, from an old working database rather than from the code.

### F12 — The flag distinguishing an unsat component already existed and was ignored

`exam_result` carries `practical_taken BOOLEAN` and `theory_taken BOOLEAN`. F10's
fabricated `'{"answer_1":"0"}'` was therefore not written because the system had no way to
say "this candidate did not sit the practical" — it had exactly that way, in a column beside
the one it overwrote.

This matters for how the rebuild guards it. A missing column is fixed by adding one; an
ignored column is not, because the next reader of the data has to know the flag exists and
must be consulted before the answer field means anything. Every query, report and export
becomes responsible for a rule that lives nowhere. **That is the argument for making the
absent case unrepresentable rather than flagged** — with theory and practical as separate
exams and separate sittings, a candidate who did not sit the practical has no practical
sitting, and there is no field to fabricate a value into and no flag to forget to check.

Found 2026-08-13, alongside F11.

### F13 — The five question types are five private JSON schemas that disagree

Every layout beyond plain text stores structured data as JSON inside a `VARCHAR` column,
and no two types agree on how to name the same thing. Across 89 questions:

- The location of an image is `path` in types 2 and 3, `location` in type 4's stem, and
  `image_location` in types 4 and 5's options. Three keys for one concept, two of them
  inside the same question type.
- Type 1's practical option payload is keyed `quesiton_type` — a misspelling shipped in
  data, not in code. A reader spelling it correctly gets nothing, and cannot distinguish
  that from a legitimately absent value.
- Type 3's options carry a single key `q_a`, which names the option rather than describing
  its content.
- A stem is `{heading, question}` in one shape and `{images, question}` in another.
- `question_images` holds a `videos` key — a column named for images, holding video.
- The discriminator inside every payload, `"type"`, has exactly one value across all 188
  occurrences: `"image"`. It discriminates nothing.
- `table_columns` appears 12 times and is always `4`, and the grid it describes is a
  `path` object of `{filename, location}` where `location` is a list of four names.

**Five bespoke unpacking functions in `exam_utils.py` was the symptom; five bespoke
serialisations is the cause.** A sixth layout could reuse none of it, and a correction to
one type's key names reaches no other type — F1's family, in the content model rather than
the results.

The rebuild's content blocks replace all five: a stem is an ordered list of blocks and so
is an option, so a new layout is new rows. Nothing has to agree on key names because there
are no keys.

Note what this *does* settle: the image grid is no longer hypothetical. It is always four
columns, it occurs twelve times, and its content is four image references sharing a
location. That is a known requirement to design against rather than a guess — see the
questions-app plan, Task 5.

Found 2026-08-15, in `rhytmic_master.db`.

### F14 — The practical answer key is joined to its questions by convention, not by key

`exam_practial_answers` holds 20 rows — `Rope, Hoop, Ball, Clubs, Ribbon` against four
aspects. It carries no foreign key to anything. A row's identity is an
`internal_question_value` with 20 distinct values, a `result_question_value` with only 4,
and a `decipline` string; the questions those scores belong to are four separate rows in
`exam_questions`, each holding five video filenames. **Nothing in the schema connects the
two.** The join is positional order plus string agreement, which is F2's key mismatch with
a second table added to it.

**This is a migration finding, not a design one.** The rebuild already makes the shape
unrepresentable — `PracticalItem(routine, aspect, expert_score)` carries a real foreign key
and a real `UNIQUE (routine, aspect)`, so an expert score cannot exist without naming
exactly which cell of the 4 × 5 grid it belongs to. There is nothing to fix in the new
models.

The risk is entirely in the import. Reconstructing routine ↔ aspect ↔ score from positional
convention has one dominant failure mode: an off-by-one shifts every expert score by one
apparatus and produces twenty plausible marks that are all wrong. Nothing in the source data
can detect it, because the ordering *is* the key. Any importer must therefore reconstruct
the mapping from the `decipline` and `result_question_value` strings and assert the 5 × 4
grid is complete before writing a single row — never from row order.

Note also that `control_score`, the expert score itself, is `VARCHAR(64)` holding three
characters. **The expert score is text**, which is exactly the comparison F3 gets wrong, and
the import is where it stops being text.

For context on how the practical was stored: those four question rows carry
`question_type = '1'` — the same type as a plain four-option theory question — with a JSON
stem, a `question_images` column holding a `videos` key, and four unused option columns all
answered `'A'`. That shape is why the two tables were never linked; it had nowhere to put a
relationship. Splitting theory from practical was decided on 2026-08-10, before this
database was read.

Found 2026-08-15, in `rhytmic_master.db`.

### F15 — The JSON payloads do not fit the columns that hold them

`exam_questions` declares `question VARCHAR(200)` and `option_a`–`option_d VARCHAR(64)`.
The data reaches 340 characters in `question`, and 275 in `option_b` and `option_c`.

SQLite does not enforce declared widths, so this was invisible for the life of the app.
Postgres does. **The legacy question bank cannot be loaded into its own declared schema on
any database that enforces types** — a migration has to widen the columns first, which is
the schema conceding that the varchars were never holding what they claimed to.

Nothing was truncated and no data was lost. The finding is that the declaration and the
content have contradicted each other unnoticed for the life of the system, and the only
reason it never bit is the choice of engine. Any port that assumed the declared widths were
real — including the deleted FastAPI one — was working from a schema that had already been
overruled by its own data.

Found 2026-08-15, in `rhytmic_master.db`.

## Scope

### In

- Multiple exams, levels and sittings as first-class entities
- A composable content model that removes question types 1–5
- Immutable, auditable sitting records
- Reproducible, unit-tested scoring, driven by data tables
- Google-only authentication; roster-based authorisation
- Certification history as an immutable event log

### Out

- Practice mode
- A visual question-authoring editor (Django admin plus a preview link instead)
- Cohort analytics and per-question difficulty statistics
- Multi-federation / multi-tenant support
- Difficulty (DB/DA) marking and sequence alignment — see "Deferred" below

### Deferred, with a known slot

FIG's Difficulty components are marked by aligning the candidate's chronological sequence
of difficulty values against the expert's using a weighted edit distance, then converting
total error to a percentage by table. The practical exam scores **Execution only** for now,
so this is out of scope. It slots in later as an additional component type with its own
marking algorithm; the component/table structure below is designed to accept it without
schema change.

## Architecture

One Django project, one deployment, Postgres, with a Vite-built React bundle mounted on a
single page.

```
rhythmic/
├── config/              # settings, urls, wsgi
├── accounts/            # User, JudgeProfile, roster import, allauth, permissions
│                        # User lands early - AUTH_USER_MODEL must be set before
│                        # anything points a foreign key at it. The rest follows later.
├── questions/           # question bank and content model
├── exams/               # exam definitions, sittings, certification
├── scoring/             # plain Python. No Django import. No database.
├── frontend/            # Vite + React + TypeScript → static/
├── tests/               # one subdirectory per package above
├── compose.yaml
└── pyproject.toml
```

Tests are collected under a single `rhythmic/tests/`, one subdirectory per package —
`tests/scoring/`, `tests/questions/`, `tests/exams/`, `tests/config/`. **`tests/` and
every subdirectory need an `__init__.py`**; see the note under Layout in `CLAUDE.md`
for the two distinct ways collection breaks without them.

### Why Django

The admin is the reason. Exam officials author questions and manage rosters; generating
those screens from model definitions removes the largest chunk of frontend work and
directly addresses problem 4. The admin is generated from Django ORM models, so this choice
also means leaving SQLAlchemy behind.

### Why a React island rather than a SPA

Of the six screens this system needs, five are forms and tables. Exactly one — the practical
exam runner — has genuine client-side state: video playback, per-exercise progress, and no
going back. The old code forced that statefulness through a stateless form-post model, one
full page POST per video, which is why `practical_exam()` interleaves progress arithmetic,
answer accumulation, persistence and rendering in a single function.

So: Django serves everything; `/sitting/<id>` mounts a React + TypeScript application.
Same origin, so the island inherits the session cookie. No CORS, no token storage, no
second deployment.

### Why `scoring/` is not a Django app

It is an ordinary Python package importing nothing from Django and touching no database.
Plain dataclasses in, plain dataclasses out. This is what makes F3–F6 testable, and it is
where every marking algorithm lives.

### Postgres

At this scale SQLite would cope. Postgres is chosen for transferability and because
`compose.yaml` running app plus database is the most useful deployment artefact to
understand. This is a learning-driven choice, stated as such.

## Authentication and authorisation

### Authentication — Google only

OAuth 2.0 Authorization Code flow with PKCE, via `django-allauth`. No passwords, no reset
flow, no password hashing. Google's ID token is verified and then discarded; the app issues
an ordinary Django session cookie. Session cookies rather than JWTs: same-origin server-
rendered app, and revocation stays instant.

Adding a second provider later (e.g. Microsoft) is configuration, not redesign.

### Authorisation — entirely local

Google answers exactly one question: is this really this email address. Everything else is
local:

- **Permissions via Django Groups.** Views check permissions, never group membership, so
  reassigning capability is admin work rather than a deploy.
- **Role-specific data in its own model.** `JudgeProfile` carries SAGF identity. Officials
  do not have one.

Two roles at launch — Candidate and Exam Official — plus superuser. Officials administer
exams, certify results and publish them. They never hand-mark: all marking is automatic.

### Identity binding

Registration inverts. Today a stranger self-registers and an admin later flips `enabled`.
Instead, an official imports the SAGF roster of eligible judges; a candidate signs in with
Google; the system matches their Google-verified email against the roster. No match, no
entry. Open signup is disabled.

This gives officials one bulk action instead of many reactive ones, and it binds the account
that sat the exam to a verified address on the federation's own roster — which is what makes
a disputed result defensible.

### Eligibility

> **Amended 2026-09-25** by `2026-09-25-judge-records-design.md`: eligibility no longer consults certification history. Level chooses the paper; category is the award, and history feeds the award's bounds instead.


A judge never edits their own level. "Level" today conflates two different things:

| | Meaning | Controlled by |
|---|---|---|
| Certification level | What they have already achieved | Nobody — it is an outcome |
| Exam being attempted | What they intend to sit | Judge selects, system validates |

Certification level is therefore derived, not stored: the highest `Certification` a judge
holds. A judge selects an exam to attempt; the system checks eligibility.

**Roster and records must agree.** A judge may sit an exam only if this year's roster
permits that level *and* their certification history supports it. Disagreements are flagged
to an official to resolve explicitly. An override **must** record who made it and why —
a blank reason field is worse than none, because it resembles an audit trail without being
one.

## Domain model

### Accounts

> **Amended 2026-09-25** by `2026-09-25-judge-records-design.md`: `Certification` records a **category** (1–4 or fail), not a level; it lives in `exams`, and its `judge` points at `JudgeProfile`.


```
User                 Django user. Identity from Google. No password.
JudgeProfile         sagf_id. One per candidate.
Certification        IMMUTABLE. judge · level · awarded_on · sitting · certified_by
RosterEntry          Imported from SAGF. sagf_id · email · levels permitted · year
```

Current level is computed as the highest certification held. History — who awarded it, when,
off which sitting — comes free.

### Questions

The five question types collapse into one shape. Across all of them, only two things vary:
what the stem is made of, and what each option is made of. Both are drawn from a small
vocabulary: text, image, image-grid, video.

```
Question             the theory question
  QuestionBlock      ordered. kind + payload + optional media
Option               ordered. exactly one flagged correct
  OptionBlock        ordered. kind + payload + optional media

Apparatus            name + display order. A table, not a choice field.
Routine              apparatus + video. Exists once.
PracticalItem        routine + aspect (DA|DB|AV|EX) + expert score
```

`QuestionBlock` and `OptionBlock` share an abstract base model.

**Presentation is data; marking is behaviour.** There are five layouts and one marking
scheme for theory. A new layout is new data, not new code.

**Revised 2026-08-10: theory and practical are separate models.** This section
originally had a single `Question` with `marking_scheme: CHOICE | NUMERIC`. The
collapse-into-one-shape argument is sound for the five *theory* layouts, which really
do differ only in block content — it was extended to cover the practical before anyone
had established what a practical item contains.

**The practical asks nothing about the routine.** The candidate watches it and enters a
number; there is no stem and there are no options. So a practical item holds a routine,
an aspect and an expert score, and shares nothing with a theory question but a position
in a component. One model spanning both means every row carries half its columns null,
with a discriminator saying which half to ignore.

Two things corroborate the split. `scoring/` already separates them —
`mark_choice(response, correct_option)` and `mark_numeric(response, expert_score, table)`
share no argument but the response. And `ExamComponent` already knows which kind it
holds, per this spec's own description of it.

One routine is referenced by four `PracticalItem` rows, one per aspect — never copied
into each. Four rows each owning the same upload means replacing a video has to find
all four, and a missed copy has a candidate judging `EX` against last year's routine
with no error anywhere. Same argument as questions shared across levels.

**Content blocks are relational rows, not JSON.** In Django the editing UI is generated from
the models, so JSON content would mean building a custom editor — the expensive frontend
work explicitly out of scope. Rows give a usable authoring screen for free.

**Media is uploaded, never path-typed.** Blocks own an `ImageField`/`FileField`. This
replaces the `static/exam_images/q17/q17_a_1.jpg` naming convention, which nothing
validated and which broke silently on rename.

**Editing is free, and logged.** Because sittings freeze their own copy (below), editing a
question can no longer corrupt history. Version chains were considered and rejected as a
second mechanism guaranteeing a property snapshots already guarantee. `django-simple-history`
provides attributed edit history and rollback for a line per model — infrastructure, not a
domain concept.

**A `[Preview]` action** renders the real candidate view of a draft question, because the
admin form cannot show an official what a question will look like.

### Exams and sittings

```
Exam                 level · year
  ExamComponent      one per marked section of the exam:
                       Theory    → CHOICE questions, no marking table
                       Execution → NUMERIC questions, one marking table
                     each carries its own grade bands
Sitting              judge · exam · status
                     started_at · submitted_at
                     certified_at · certified_by · outcome
SittingItem          FROZEN AT SITTING START
                     sitting · position
                     question_snapshot   JSONB   as presented
                     marking_key         JSONB   correct option, or expert score
                     response            JSONB   what the candidate gave
                     marks_awarded               computed at submission, STORED
                     max_marks
```

`status`: `pending → in_progress → submitted → certified`. A pending sitting *is* the
enrolment; no separate model.

**Freeze at start, not at submission.** The question set is snapshotted when the candidate
begins. This fixes a live defect — `theory_exam()` re-queries the bank on every GET, so a
reload could serve a different set, which is why the `theory_loaded` cookie exists to forbid
reloading. With freeze-at-start, reload is safe: same sitting, resumed. The practical exam's
hand-rolled progress tracking collapses into "which items have a response yet".

**Marks are stored, not recomputed.** This is the fix for F1. Displaying a result never
touches the question bank.

**Scoring and certification are separate events.** Scoring produces a number; an official
produces the outcome, at a different time, recorded against their name.

**JSONB appears here and nowhere else.** Live content is relational because it is *edited*;
frozen content is JSON because it is *recorded* — written once, never queried into, read back
whole. Storage follows lifecycle, not data shape.

## Scoring

`scoring/` holds algorithms; the database holds numbers. FIG republishes its marking tables
every cycle and does not finalise them until after the first examination has been sat, so
any hardcoded table is a guaranteed rewrite.

### Execution marking

A marking table is a two-dimensional band lookup:

- **row** — the band the expert's deduction falls in
- **column** — the band the absolute difference falls in
- **cell** — the percentage awarded

Band lookup rather than exact indexing is what fixes F4 structurally: there is no index to
miss. Comparison is on `Decimal`, not `float` or string, which fixes F3.

The existing SAGF scheme is expressible as a single-row table (columns at 0.05 intervals,
95% down to 0%, then 0). Loading it that way reproduces today's behaviour minus F3 and F4,
requires no policy change from the federation, and lets officials adopt the current Code of
Points by adding rows in the admin rather than by a code change. FIG's own two-dimensional
Execution tables load into the same structure unchanged.

### Pipeline

```python
mark_choice(response, key)         -> Marks
mark_numeric(response, key, table) -> Marks       # implements Execution marking
score_component(items)             -> Percentage  # mean across exercises
grade(percentage, bands)           -> Grade       # Excellent … Fail
```

`mark_numeric` is named for the marking scheme, not the component, so that any future
band-lookup component reuses it unchanged.

Component percentages are the **mean of per-exercise percentages**, never a raw mark total
(F5). Grade bands are data, per exam.

Django's role is to load rows, hand plain data to `scoring/`, and record what comes back.

## Testing

The rule this project adopts: **scoring rules get tests first.** A wrong score is invisible —
it looks exactly like a right score — so it is the one place where absence of tests is not
recoverable by observation.

- `scoring/` — unit tests, no database, no fixtures. F3 and F4 become regression tests
  written before the replacement is implemented. FIG's published worked examples serve as
  test data if the difficulty component is ever added.
- Eligibility rules — unit tests, pure inputs.
- Snapshot integrity — a test that edits a question after a sitting is submitted and asserts
  the recorded marks and snapshot are unchanged. This is F1 as an executable guarantee.
- Views and permissions — Django test client. Every admin route asserted to reject a
  non-official, which F7 would have caught.
- The React island — component tests for the runner's state machine.

## Operations

- `compose.yaml`: application plus Postgres.
- Media (images, exam video) on a mounted volume in development; object storage in
  production. Exam video is large and should not live in the image or the repository.
- Secrets, including the Google OAuth client secret, from the environment. Never committed.
- Roster import as an admin action with a dry-run that reports what would change.

### Data protection

Candidate records are personal data under POPIA and are retained indefinitely, because
certification history is the point of the system. Retention is therefore justified by
purpose, but the justification should be stated in a privacy note and the roster import
should not collect fields the exam does not need.

## A note on size

This is one system, not several: authentication feeds authorisation, authorisation gates
sittings, sittings freeze content, and scoring consumes what they freeze. Splitting it into
separate specs would mean specifying the same interfaces twice.

It is, however, more than one sitting's work, and the implementation plan is expected to
sequence it — domain model and scoring first, where the correctness risk is, and the React
island last, where the learning curve is steepest and the requirements are already settled
by everything before it.

## Open questions

1. **Which Code of Points cycle does the SAGF national exam follow?** The existing answer key
   uses `D1 + D2` / `D3 + D4` / `AV` / `EX`, which is 2017–2020 structure; the current cycle
   has no D1–D4 and no AV. This does not block implementation — the table structure absorbs
   either — but the initial table data must come from whatever SAGF actually publishes.
2. **Number of candidates per sitting.** Assumed tens. Nothing in this design depends on it,
   but it would confirm Postgres is comfortably oversized rather than necessary.

## Reference — FIG 2025–2028

Source documents, read on 2026-07-28:

- [RG Specific Judges' Rules 2025–2028](https://www.gymnastics.sport/publicdir/rules/files/en_1.3%20-%20RG%20Specific%20Judges'%20Rules%202025-2028%20(mark-up).pdf)
  — marking tables, evaluation scale, exam composition
- [General Judges' Rules 2025–2028](https://www.gymnastics.sport/publicdir/rules/files/en_1.2%20-%20General%20Judges'%20Rules%202025-2028.pdf)
  — category requirements, examination process

### Execution marking (the shape this design targets)

Judges give one total deduction per exercise. The percentage awarded is a
**two-dimensional** lookup: how far the candidate was from the expert score, *and*
which band the expert's own deduction fell in. Tolerance widens as the routine gets
harder to judge.

| Expert's deduction | off by 0.3 | off by 0.9 |
|---|---|---|
| ≤ 1.00 | 80% | 0% |
| 2.1 – 2.5 | 90% | 40% |
| 3.6 – 4.0 | 100% | 50% |

The component score is the **mean** of per-exercise percentages, over 12 exercises
for individual and 6 for group.

### Evaluation scale

| Grade | Difficulty (DB/DA) | Artistry / Execution |
|---|---|---|
| Excellent | 80–100% | 90–100% |
| Very Good | 70–79.99% | 80–89.99% |
| Good | 60–69.99% | 65–79.99% |
| Pass | 50–59.99% | 50–64.99% |
| Fail | < 50% | < 50% |

### Categories — General Judges' Rules §2.6, read 2026-08-10

**SAGF follows FIG** (confirmed by Altus, 2026-08-10), so this table is the rule, not
a template.

| | Category 1 | Category 2 | Category 3 | Category 4 |
|---|---|---|---|---|
| **Difficulty** | excellent | very good | good | pass |
| **Execution** | very good | very good | good | pass |
| **Artistry** | very good | very good | good | pass |

The award is the highest category whose three minimums are *all* met — the weakest
aspect caps it. **Category 1 is the only asymmetric row**: Difficulty must be
excellent while Execution and Artistry need only very good. Categories 2–4 are
uniform. Do not "correct" that asymmetry.

Below Category 4 is **fail**, a fifth outcome rather than a category. The scale is
explicitly five-valued — *"excellent, very good, good, pass, fail"* (§2.2.1) — and
§2.7.2 gives failure its own retest path, requiring the entire course and examination
again.

`Difficulty` here is one value. Since the exam scores `DA` and `DB` separately, it is
their mean — see `CLAUDE.md`, decided 2026-08-08.

### The examination result is an upper bound, not the award

> **Amended 2026-09-25** by `2026-09-25-judge-records-design.md`: the `min(…)` formula below is wrong. The drop limit is a **floor**, not a cap — a previous Category 1 judge examined at Category 4 is awarded Category 3.


This is the part that changes the design, and it is why scoring and certification are
separate events in this system.

> *"A judge who has not met the judging experience requirements for the Category
> earned in the examinations will receive the category in accordance with the
> competitions successfully judged."* — §2.6

Three further caps, all from §2.6:

- *"A first time Brevet can achieve a maximum of Category 3 in his/her first cycle."*
- *"a judge can only drop 2 categories in one cycle: i.e. Category 1 can drop at
  worst to Category 3, Category 2 can drop at worst to Category 4."*
- Category 1 experience must be met **before** the Intercontinental Course; there is
  no upgrade to Category 1 afterwards.

So the awarded category is roughly
`min(examination result, experience, first-cycle cap, previous − 2)`.

The exam system computes the examination result and stops there. Awarding consumes
that result alongside judging history the exam knows nothing about, which is exactly
why an official produces the outcome at a different time and it is recorded against
their name.

### Why none of these numbers are in the code

FIG states: *"All those tables are provisional until Intercontinental Course table
scale is fixed. Once fixed by FIG TC, it will remain for the rest of the cycle."*
The scale is set by the Technical Committee **after the first examination is sat**,
then applied for the remaining four years. Any table hardcoded in Python is a
guaranteed rewrite in 2029.

### Difficulty marking, for whenever it is picked up

Not implemented — Execution only. Recorded so the method does not have to be
rediscovered.

The candidate lists each difficulty value in chronological order. FIG compares that
sequence to the expert's using a weighted edit distance ("a modified Levenshtein
algorithm"), evaluating every order-preserving alignment and taking the one with the
**lowest** total error for the candidate. Total error then converts to a percentage
by table. FIG's own worked example:

```
Expert:      0.6  0.6  0.4  0.0  0.9  0.0  0.9
Candidate:   0.6  0.5  0.4  0.8  0.5  0.9

alignment 1 → 0.0  0.1  0.0  0.8  0.4  0.9  0.9   = 3.1
alignment 2 → 0.0  0.1  0.0  0.1  0.5  0.0  0.0   = 0.7   ← chosen
```

Position-by-position comparison would punish a single omission across every element
that follows it. Alignment charges for the omission alone. Those two rows make good
first test cases if this is ever built.
