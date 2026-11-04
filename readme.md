# Rhythmic Exam

Online certification exam for SAGF rhythmic gymnastics judges. It runs the
examination, marks it against the published tables, and records the result in a
form that holds up if a candidate disputes it.

Two exams, enrolled for separately and never combined:

- **Practical** — the real certification. Five routines, one per apparatus, each
  judged on four aspects (`DA`, `DB`, `AV`, `EX`): twenty marks, each compared
  against an expert score.
- **Theory** — multiple choice. Kept to exercise the question formats; it does not
  decide a category.

The system computes the examination category. The awarded category is a separate
act, recorded against the official who makes it.

## Layout

```
rhythmic/              the system — Django project plus a framework-free core
  scoring/             marking and grading; imports no framework, touches no database
  questions/           question content: theory questions, routines, apparatus, media
  exams/               exam definitions, sittings, the freeze, marking, results
  accounts/            judges, the roster, certification
  config/              Django settings and URLs
  tests/               one subdirectory per package
  tools/               mutation_sweep.py
docs/superpowers/
  specs/               design documents
  plans/               implementation plans, one per stage
  decisions-log.md     why things are the way they are, commit by commit
legacy/flask_backend/  the 2023 Flask app — reference only, not maintained
tools/run_ruff.sh      lint and format rhythmic/
compose.yaml           Postgres (and pgAdmin, on request)
pytest.ini             the only pytest config
```

## Setup

Requires Python 3.12+ and Docker.

```bash
python3 -m venv .venv
.venv/bin/pip install -e "rhythmic[dev,web]"

cp .env.example .env              # then fill in the blank values
docker compose up -d              # Postgres; add --profile tools for pgAdmin

git config core.hooksPath .githooks
```

**Don't skip the last line.** The pre-commit hook in `.githooks/` runs
`ruff format --check` and `ruff check` on the staged files and blocks the commit if
either fails. Git does not pick up a hooks path from a clone, so without this line
the hook simply never runs, and nothing tells you.

Then create the schema:

```bash
cd rhythmic
../.venv/bin/python manage.py migrate
```

## Checks

Run these from `rhythmic/`, where the ruff rule set lives:

```bash
../.venv/bin/pytest
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
```

Most tests need Postgres running. The `scoring/` tests do not.

`tools/mutation_sweep.py` breaks the code one claim at a time and checks that some
test notices. It takes about twenty-five minutes and is run at the end of each task:

```bash
../.venv/bin/python tools/mutation_sweep.py
```

Any `SURVIVED` line means a change to the code that no test caught.

## Status

Being rebuilt from the ground up. The design is in
[`docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md`](docs/superpowers/specs/2026-07-28-rhythmic-exam-rebuild-design.md),
including the findings from the old app that the rebuild exists to fix. Work is
sequenced by the plans in `docs/superpowers/plans/`; the newest one is the
current stage.

The Flask app under `legacy/` is kept for two things the rebuild still needs: the
exam media, and the question templates to check new rendering against. It is not
run and not maintained. It gets deleted once the media is migrated and the block
renderers are built.

## Note on spelling

The sport is *rhythmic*. The original project and its legacy code spell it
*rhytmic*. The repository was renamed to `rhythmic_exam` on 2026-07-28; GitHub
redirects the old URL, so existing clones keep working. New code uses the correct
spelling; the legacy tree keeps the old one.

## Exam content is not in this repository

This repository is public, so the question bank and answer key are deliberately
left out. `legacy/flask_backend/doc/example_format.csv` documents the legacy import
format using made-up questions. Never commit a database file or a data file
without first checking that it contains no questions or answers. `*.db` is
gitignored for this reason.
