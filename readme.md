# Rhythmic Exam

Online certification exam for SAGF rhythmic gymnastics judges.

## Layout

```
docs/superpowers/
  specs/     design documents
  plans/     implementation plans
rhythmic/    the system (under construction)
legacy/
  flask_backend/   the 2023 Flask app — reference only, not maintained
```

## Status

Being rebuilt from the ground up. The design is in
[`docs/superpowers/specs/2026-07-28-rhytmic-exam-rebuild-design.md`](docs/superpowers/specs/2026-07-28-rhytmic-exam-rebuild-design.md);
work is sequenced by the plans in `docs/superpowers/plans/`.

The Flask app under `legacy/` is kept for two things the rebuild still needs: the
exam media, and the question templates to check new rendering against. It is not
run and not maintained. It gets deleted once the media is migrated and the block
renderers are built.

## Note on spelling

The sport is *rhythmic*. The original project, its repository, and the legacy code
all spell it *rhytmic*. New code uses the correct spelling; the legacy tree keeps
the old one.

## Exam content is not in this repository

The question bank and answer key are deliberately excluded — this repository is
public. `legacy/flask_backend/doc/example_format.csv` documents the legacy import
format using fabricated questions. Real content lives in the database and its
backups.
