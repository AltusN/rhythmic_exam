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
├── questions/           # question bank and content model
├── exams/               # exam definitions, sittings, certification
├── scoring/             # plain Python. No Django import. No database.
├── frontend/            # Vite + React + TypeScript → static/
├── tests/
├── compose.yaml
└── pyproject.toml
```

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
Question             marking_scheme: CHOICE | NUMERIC
  QuestionBlock      ordered. kind + payload + optional media
Option               ordered. exactly one flagged correct (CHOICE only)
  OptionBlock        ordered. kind + payload + optional media
```

`QuestionBlock` and `OptionBlock` share an abstract base model.

**Presentation is data; marking is behaviour.** There are two marking schemes, not five
question types. A new layout is new data, not new code.

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

Category 1 requires Difficulty excellent with Artistry and Execution very good;
Category 4 requires all three at pass.

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
