from time import time
from datetime import datetime

import jwt

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.orm import backref

from rhytmic_exam_app import db, login

from sqlalchemy import event

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    sagf_id = db.Column(db.String(64), index=True, unique=True)
    level = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(128))
    surname = db.Column(db.String(128))
    email = db.Column(db.String(128), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    enabled = db.Column(db.Boolean(), default=False)
    admin = db.Column(db.Boolean, default=False)
    answers = db.relationship("ExamResult", backref=backref("linked_user", uselist=False))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=5400):
        return jwt.encode(
            {"reset_password": self.id,"exp": time() + expires_in},
            current_app.config["SECRET_KEY"],
            algorithm="HS256"
        )

    def is_enabled(self):
        """ a 2 step proccess to actually authenticate on the website.
            Once registration requested, it must be enabled by an admin
            for now
        """
        return self.enabled

    @property
    def is_admin(self):
        """ admin can do other stuff users can't. like edit the exam 
        or update users
        """
        return self.admin

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])["reset_password"]
        except:
            return

        return User.query.get(id)

    def __repr__(self):
        return f"User <{self.username}>"

class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sagf_id = db.Column(db.Integer, db.ForeignKey("user.sagf_id"), unique=True)
    theory_answer = db.Column(db.Text) #Store as json the result set
    practical_answer = db.Column(db.Text) #Store as json
    practical_progress = db.Column(db.Text)
    exam_start_date = db.Column(db.DateTime, default=datetime.today)
    theory_taken = db.Column(db.Boolean)
    practical_taken = db.Column(db.Boolean)
    exam_end_date = db.Column(db.DateTime)

    def __repr__(self):
        return f"Result <{self.id}>, <{self.sagf_id}>"

class ExamQuestions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, index=True)
    question = db.Column(db.String(200), index=True)
    question_type = db.Column(db.String(256))
    question_images = db.Column(db.Text) # store as json the images
    option_a = db.Column(db.String(256))
    option_b = db.Column(db.String(256))
    option_c = db.Column(db.String(256))
    option_d = db.Column(db.String(256))
    answer = db.Column(db.String(1))
    exam_level = db.Column(db.String(20))
    question_category = db.Column(db.String(64))

    def __repr__(self):
        return f"Question <{self.id}>"

class ExamPractialAnswers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    decipline = db.Column(db.String(64))
    internal_question_value = db.Column(db.String(64))
    result_question_value = db.Column(db.String(64))
    control_score = db.Column(db.String(64))

@login.user_loader
def load_user(id):
    return User.query.get(int(id))