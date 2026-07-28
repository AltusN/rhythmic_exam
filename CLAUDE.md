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

- `docs/superpowers/specs/2026-07-28-rhytmic-exam-rebuild-design.md` — the design.
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

The sport is *rhythmic*. The repo, the legacy tree and the old package all spell it
*rhytmic*. **New code uses the correct spelling.** Don't "fix" the legacy tree, and
don't propagate the typo into new code.

## Hard constraints

- **No real exam content in this repository. It is public.** The question bank and
  answer key were removed on 2026-07-28. `legacy/flask_backend/doc/example_format.csv`
  is synthetic and safe. Before committing any data file, check whether it carries
  questions or answers. The 117 tracked exam images are a known pre-existing
  exposure, to be revisited at media migration.
- **`rhythmic/scoring/` imports nothing from Django and touches no database.** If a
  module there needs a framework, the boundary is wrong.
- **`Decimal` everywhere for marks and deductions, never `float`. Never compare
  answers as strings** — finding F3 is exactly that bug.
- **Marking tables and grade bands are data, never literals in Python.** FIG
  republishes them every four-year cycle and doesn't finalise them until after the
  first exam is sat.
- **Check `git status` before committing.** `git commit` commits the whole index —
  this already caused a file to be committed after Altus had declined it.

## Current state

The `rhythmic/` directory is empty. Next action is **Task 1** of the scoring plan:
Altus writes `rhythmic/pyproject.toml`, installs it editable, and gets one smoke
test passing.

He was advised to create a **fresh virtualenv** for `rhythmic/` rather than reuse
the root `.venv`, which still has Flask and SQLAlchemy in it and would let
`import flask` succeed inside the supposedly framework-free package.

Each task in the plan ends at a **review gate**. He posts the code; you review it
before he starts the next task.

## Open questions, both non-blocking

1. Which Code of Points cycle the SAGF national exam actually follows. The old
   answer key uses `D1 + D2` / `D3 + D4` / `AV` / `EX`, which is 2017–2020
   structure. Affects what table data gets loaded, not the design.
2. Candidates per sitting. Assumed tens.
