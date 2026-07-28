import csv
import sqlite3

from db_import_export import export_questions, import_questions


CREATE_TABLE_SQL = """
CREATE TABLE exam_questions(
    id INTEGER PRIMARY KEY,
    question_id INTEGER,
    question TEXT,
    question_type TEXT,
    question_images TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    answer TEXT,
    question_category TEXT,
    exam_level TEXT
);
"""


INSERT_SQL = """
INSERT INTO exam_questions(
    id,
    question_id,
    question,
    question_type,
    question_images,
    option_a,
    option_b,
    option_c,
    option_d,
    answer,
    question_category,
    exam_level
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
"""


def _seed_database(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute(
        INSERT_SQL,
        (
            1,
            100,
            "Which option is correct?",
            "1",
            "{}",
            "A",
            "B",
            "C",
            "D",
            "A",
            "theory",
            "1",
        ),
    )
    con.commit()
    con.close()


def test_export_questions_writes_expected_header_and_data(tmp_path):
    db_path = tmp_path / "rhytmic.db"
    csv_path = tmp_path / "questions.csv"
    _seed_database(str(db_path))

    export_questions(str(db_path), str(csv_path))

    with open(csv_path, newline="", encoding="utf-8") as fin:
        rows = list(csv.reader(fin))

    assert rows[0] == [
        "id",
        "question_id",
        "question",
        "question_type",
        "question_images",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "answer",
        "question_category",
        "exam_level",
    ]
    assert rows[1][0] == "1"
    assert rows[1][2] == "Which option is correct?"


def test_import_questions_replaces_existing_records(tmp_path):
    db_path = tmp_path / "rhytmic.db"
    csv_path = tmp_path / "import.csv"
    _seed_database(str(db_path))

    with open(csv_path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(
            [
                "id",
                "question_id",
                "question",
                "question_type",
                "question_images",
                "option_a",
                "option_b",
                "option_c",
                "option_d",
                "answer",
                "question_category",
                "exam_level",
            ]
        )
        writer.writerow(
            [
                2,
                200,
                "Imported question",
                "1",
                "{}",
                "Yes",
                "No",
                "Maybe",
                "N/A",
                "A",
                "theory",
                "2",
            ]
        )

    import_questions(str(db_path), str(csv_path))

    con = sqlite3.connect(db_path)
    rows = con.cursor().execute("SELECT id, question FROM exam_questions").fetchall()
    con.close()

    assert rows == [(2, "Imported question")]
