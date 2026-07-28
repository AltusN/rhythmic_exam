import os
import datetime
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# Prefer the local flask_backend env file, but also support a repo-root fallback.
load_dotenv(os.path.join(basedir, ".flaskenv"))
load_dotenv(os.path.join(os.path.dirname(basedir), ".flaskenv"))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "super duper secret keys"

    #Database stuff
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'rhytmic.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')

    #Mail stuff
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 25)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_MAX_EMAILS = 1
    try:
        ADMINS=os.environ.get("ADMINS").split()
    except:
        ADMINS=[]
    #Exam specific
    DISABLE_EXAM_DATE=int(os.environ.get("DISABLE_EXAM_DATE") or 1) # if enabled (1) then below doesn't matter
    EXAM_DATE=datetime.date.fromisoformat(os.environ.get("EXAM_DATE", "1995-01-01"))
    EXAM_DURATION=int(os.environ.get("EXAM_DURATION") or 1)