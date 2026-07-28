# Rhytmic Exam App

[![Build Status](https://travis-ci.com/AltusN/rhytmic_exam.svg?branch=master)](https://travis-ci.com/AltusN/rhytmic_exam)

Web app for running an online rhythmic gymnastics exam.

## Project Location

The application source now lives in the `flask_backend` directory.

If you are in the repository root, run:

```bash
cd flask_backend
```

before using the commands below.

## Features

- Theory exam with multiple-choice questions
- Practical exam flow with video-based questions
- Result reporting and CSV export/import support
- Admin user management

## Requirements

- Python 3.10+
- pip

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Application settings are read from environment variables (optionally via a `.flaskenv` file in the project root).

Common variables:

- `SECRET_KEY`
- `DATABASE_URL` (defaults to local SQLite: `rhytmic.db`)
- `DISABLE_EXAM_DATE` (`1` to bypass date window checks, `0` to enforce)
- `EXAM_DATE` (ISO format, for example `2026-03-15`)
- `EXAM_DURATION` (number of days)
- `ADMINS` (space-separated emails, used for notifications)

Optional mail settings:

- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`

## Database Setup

Run migrations:

```bash
flask --app rhytmic db upgrade
```

Create an initial admin user from the Flask shell:

```bash
flask --app rhytmic shell
```

```python
u1 = User(username="admin", sagf_id="A0001", name="Admin", surname="User", email="admin@example.com")
u1.set_password("change-me")
u1.enabled = True
u1.admin = True
db.session.add(u1)
db.session.commit()
```

## Run Locally

```bash
flask --app rhytmic run
```

The app will be available at `http://127.0.0.1:5000` by default.

## Tests

```bash
pytest
```

## Import/Export Exam Questions

Use the helper script:

```bash
python db_import_export.py
```

Modes:

- `i`: Import question CSV into `exam_questions`
- `e`: Export `exam_questions` to CSV
- `ee`: Export all table names

Non-interactive usage:

```bash
python db_import_export.py i rhytmic.db doc/example.csv
python db_import_export.py e rhytmic.db exported_questions.csv
```

## Authoring Exam Questions

Detailed examples are in `doc/Using Gym Exam.docx`. The key points are summarized here.

Open the question editor at `/add_question` (authentication may be required).

Theory question types:

- Type 1: Plain text question with standard options A-D.
- Type 2: Image table question. `question_images` must be JSON with image `location` and `filename` list.
- Type 3: Plain text question, image JSON for `question_images`, and options as JSON list using identifier `q_a`.
- Type 4: Plain text question with image JSON in `question_images`; options are JSON objects with optional `image_location` and `text`.
- Type 5: Rich question JSON with placeholder tags (`<q_1>`, `<q_2>`) and matching image list. Options also use JSON for image/text combinations.

Example JSON snippets used by the app:

```json
{"type":"image", "table_columns":"4", "path": {"location":"static/q17", "filename":["q17_q_1.jpg","q17_q_2.jpg","q17_q_3.jpg","q17_q_4.jpg"]}}
```

```json
{"q_a":["0.30","0.10","0.30","0.20"]}
```

```json
{"question":"... <q_1> ...","images":["static/q23/q23_q_1.jpg"]}
```

Practical question format:

- Question field JSON:

```json
{"heading":"Scoring D1 + D2","question":"What is the value of D1 + D2?"}
```

- `question_images` JSON with video list:

```json
{"videos":["static/test_videos/1.mp4","static/test_videos/2.mp4","static/test_videos/3.mp4","static/test_videos/4.mp4","static/test_videos/5.mp4"]}
```

- Options are required by the form for practical questions but are not used by scoring logic.

## Notes

- No localisation support yet.
- Project name and module paths intentionally use `rhytmic` for compatibility with the existing codebase.
