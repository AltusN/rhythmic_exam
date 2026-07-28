from flask import Blueprint

bp = Blueprint("auth", __name__)

from rhytmic_exam_app.auth import routes