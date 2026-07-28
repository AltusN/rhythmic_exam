import datetime

from flask import Flask

from rhytmic_exam_app.auth.routes import is_exam_active


def test_is_exam_active_returns_true_when_disabled_flag_is_set():
    app = Flask(__name__)
    app.config["DISABLE_EXAM_DATE"] = 1
    app.config["EXAM_DATE"] = datetime.date(2030, 1, 1)
    app.config["EXAM_DURATION"] = 1

    with app.app_context():
        assert is_exam_active() is True


def test_is_exam_active_returns_true_inside_exam_window():
    app = Flask(__name__)
    today = datetime.date.today()

    app.config["DISABLE_EXAM_DATE"] = 0
    app.config["EXAM_DATE"] = today - datetime.timedelta(days=1)
    app.config["EXAM_DURATION"] = 3

    with app.app_context():
        assert is_exam_active() is True


def test_is_exam_active_returns_false_outside_exam_window():
    app = Flask(__name__)
    today = datetime.date.today()

    app.config["DISABLE_EXAM_DATE"] = 0
    app.config["EXAM_DATE"] = today + datetime.timedelta(days=5)
    app.config["EXAM_DURATION"] = 2

    with app.app_context():
        assert is_exam_active() is False
