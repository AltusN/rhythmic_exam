from flask import Blueprint

bp = Blueprint("errors", __name__)

from rhytmic_exam_app.errors import handlers