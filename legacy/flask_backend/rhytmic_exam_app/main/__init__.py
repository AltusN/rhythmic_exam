from flask import Blueprint

bp = Blueprint("main", __name__)

from rhytmic_exam_app.main import routes