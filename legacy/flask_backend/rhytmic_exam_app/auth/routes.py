import datetime
from urllib.parse import urlparse

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy.exc import IntegrityError

from rhytmic_exam_app import db
from rhytmic_exam_app.models import User
#auth module
from rhytmic_exam_app.auth import bp
from ..auth.forms import (
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
    ResetPasswordRequestForm
)
from ..auth.email import send_password_reset_email, send_email

@bp.route("/login", methods=("GET","POST"))
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        #Get the user from the database
        user = User.query.filter_by(username = form.username.data).first()
        #check if it's a valid login attempt
        if not user or not user.check_password(form.password.data):
            flash("Invalid username or password", "danger")
            return redirect(url_for("auth.login"))
        if not user.is_enabled():
            flash("Your login has not been enabled yet by an administrator.", "warning")
            return redirect(url_for("auth.login"))

        if not is_exam_active() and not user.is_admin:
            flash("Today's date does not fall in the exam date range. Please try again later", "danger")
            return redirect(url_for("main.index"))
                
        login_user(user, remember = form.remember_me.data)
        current_app.logger.info("%s has logged in", user.name)
        next_page = request.args.get("next")

        if not next_page or urlparse(next_page).netloc:
            flash("Logged in successfully", "success")
            next_page = url_for("main.dashboard")
        
        return redirect(next_page)
    
    return render_template("auth/login.html", title="Sign In", form=form)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))

@bp.route("/register", methods=("GET", "POST"))
def register():
    if current_user.is_authenticated:
        flash("You already have an account. Log out to create a new one", "info")
        return redirect(url_for("main.index"))

    form = RegistrationForm()

    #email is required and is stopped on the frontend.. if there is no email, this wil break anyway
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        sagf_id = (form.sagf_id.data or "").strip()
        name = (form.name.data or "").strip()
        surname = (form.surname.data or "").strip()
        email = (form.email.data or "").strip().lower()
        level = (form.level.data or "").strip()
        password = form.password.data or ""

        user = User()
        user.username = username
        user.sagf_id = sagf_id
        user.name = name
        user.surname = surname
        user.email = email
        user.level = level
        user.set_password(password)
        user.enabled = True
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            flash(f"An user combination with {form.name.data} {form.surname.data} and email {form.email.data} already exists", "danger")
            db.session.rollback()
            return redirect(url_for("auth.register"))
        #Now the user is in the database, send an email to admin to request activation
        send_email(
            "Rhytmic Exam - New User Registration",
            sender="no-reply.rhytmic_exam.co.za",
            recipients=[current_app.config["ADMINS"][0]],
            text_body=render_template("email/new_user.txt"),
            html_body=render_template("email/new_user.html")
        )

        flash("Account created. Please login to continue", "info")
        return redirect(url_for("main.index"))
    
    return render_template("auth/register.html", title="Register", form=form)

@bp.route("/reset_password_request", methods=("GET", "POST"))
def reset_password_request():
    if current_user.is_authenticated:
        flash("You're already logged in")
        return redirect(url_for("main.dashboard"))

    form = ResetPasswordRequestForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            current_app.logger.info("%s requested password reset", user.name)
            send_password_reset_email(user)
        #flash even if there isn't a valid user
        flash("Password reset request has been queued. You will revceive an email soon with instructions.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password_request.html", title="Reset Password", form=form)

@bp.route("/reset_password/<token>", methods=("GET","POST"))
def reset_password(token):
    # if current_user.is_authenticated:
    #     return redirect(url_for("index"))

    user = User.verify_reset_password_token(token)

    if not user:
        flash("Reset token could not be validated or has expired", "danger")
        return redirect(url_for("main.index"))
    
    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password update successfully", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", title="Reset Password", form=form)

@bp.route("/reset")
@login_required
def reset():
    u = User.query.filter_by(id=current_user.id).first_or_404()

    token = u.get_reset_password_token()

    return redirect(url_for('auth.reset_password', token=token))

@bp.route("/profile/<string:username>")
@login_required
def profile(username):
    return render_template("auth/profile.html")

def is_exam_active():
    ''' Simply checks if today's date is an active exam date '''

    #if the exam is disabled, then return false 
    if current_app.config["DISABLE_EXAM_DATE"]:
        return True

    today = datetime.date.today()
    exam_start_date = current_app.config["EXAM_DATE"]
    exam_end_date = exam_start_date + datetime.timedelta(current_app.config["EXAM_DURATION"])
    
    #return if the exam 
    return today >= exam_start_date and today <= exam_end_date

