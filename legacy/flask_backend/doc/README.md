# Legacy question format documentation

Reference material for the old Flask app's question format. Kept because the
rebuild has to migrate the existing question bank, and understanding how the old
data encodes is a prerequisite for that.

## Files

- **`design.txt`** — prose description of question types 1–5 and the JSON each one
  expects.
- **`Using Gym Exam.docx`** — the authoring guide given to exam officials.
- **`example_format.csv`** — a machine-readable example of the import format: one
  row per question type 1–5, plus a practical row.

## example_format.csv is synthetic

Its questions, options and answers are **fabricated**. It exists to document the
CSV *shape*, not to carry content.

The real export — 89 live questions including the answer column — was deleted from
this project on 2026-07-28 and is not in git history. This repository is public,
and an exam whose answer key is published is not an exam. Real question content
belongs in the database and its backups.

**If you are adding a data file here, check first whether it carries questions or
answers.** The `.gitignore` blanket-ignores `*.csv` for this reason, with a single
explicit exception for `example_format.csv`.

## Note on the format itself

The old schema stores `option_a`–`option_d` as `String(256)`, so any question that
isn't four short strings smuggles a JSON document into a varchar and declares a new
`question_type`. That is the rigidity the rebuild exists to remove — see the
findings in `docs/superpowers/specs/`. Read these files as a description of a
problem, not as a model to copy.

One artefact worth knowing about if you write a migration: the practical rows carry
`{"quesiton_type": "text"}` — the key is misspelled in the real data. Nothing ever
reads it, which is why the typo survived. `example_format.csv` uses the correct
spelling, since nothing depends on either.
