from flask_wtf import FlaskForm
from wtforms import RadioField, SubmitField, StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length

from rhytmic_exam_app.models import User

class AddExamQuestionsForm(FlaskForm):
    question = TextAreaField("Question", validators=[DataRequired()])
    question_type = SelectField("Question Type", choices=[
        ("1", "Type 1"),
        ("2", "Type 2"),
        ("3", "Type 3"),
        ("4", "Type 4"),
        ("5", "Type 5")
        ])
    question_images = StringField("Question Images")
    option_a = TextAreaField("Option A", validators=[DataRequired()])
    option_b = TextAreaField("Option B", validators=[DataRequired()])
    option_c = TextAreaField("Option C", validators=[DataRequired()])
    option_d = TextAreaField("Option D", validators=[DataRequired()])
    answer = SelectField("Answer", choices=[
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
    ])
    exam_level = SelectField("Exam Level", choices=[
        ("1","1"),
        ("2","2"),
        ("3","3"),
    ])
    question_category = SelectField("Question Category", choices=[
        ("theory", "Theory"),
        ("practical", "Practical"),
    ])
    submit = SubmitField()

class Disclaimer(FlaskForm):
    agree = BooleanField("Agree", validators=[DataRequired()])
    
    submit = SubmitField()

class UserEditForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    surname = StringField("Surname", validators=[DataRequired()])
    sagf_id = StringField("SAGF ID", validators=[DataRequired()])
    email = StringField("Email Address", validators=[DataRequired(), Email()])
    password = PasswordField("Password")
    password2 = PasswordField("Repear Password", validators=[EqualTo("password")])
    enabled = BooleanField("Enabled")
    admin = BooleanField("Admin User")

    submit = SubmitField()
