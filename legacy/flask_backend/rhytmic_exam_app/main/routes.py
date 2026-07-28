import json
import datetime
import csv
from functools import wraps
from io import StringIO

from flask import render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import current_user, login_required

from sqlalchemy import and_

from rhytmic_exam_app import db
from rhytmic_exam_app.main.forms import (
    AddExamQuestionsForm,
    Disclaimer,
    UserEditForm
)

from rhytmic_exam_app.email import send_email

from rhytmic_exam_app.main.exam_utils import make_question_for_exam, calculate_theory_score, calculate_practical_score

from rhytmic_exam_app.models import User, ExamQuestions, ExamResult, ExamPractialAnswers

from rhytmic_exam_app.main import bp

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        user = User.query.filter_by(id=current_user.id).first()
        if user and user.is_admin:
            return f(*args, **kwargs)
        else:
            flash("You must be logged in as an admininstrative user to perform this action", "danger")
            return redirect(url_for("main.index"))
    return wrap

# @bp.route("/")
# def coming_soon():
#     return render_template("coming.html")

@bp.route("/")
@bp.route("/index")
def index():
    user_agent = request.user_agent.platform
    exam_start_date = current_app.config["EXAM_DATE"]
    return render_template("index.html", title="Home", user_agent=user_agent, exam_date=exam_start_date)

@bp.route("/user_admin", methods=("GET", "POST"))
@login_required
@admin_required
def user_admin():
    page = request.args.get("page", 1, type=int)

    users = User.query.paginate(page=page , per_page=8)
    
    return render_template("exam/user_admin.html", title="User Admin", users=users)

@bp.route("/update_user/<int:id>", methods=("GET", "POST"))
@login_required
def update_user(id):
    user = User.query.filter_by(id=id).first_or_404()

    form = UserEditForm()

    if form.validate_on_submit(): 
        notify_user = False
        #Don't update the username
        user.name = form.name.data
        user.surname = form.surname.data
        user.email = form.email.data
        if not user.enabled and form.enabled.data:
            #then the user was not enabled previously but is now
            notify_user = True
        user.enabled = form.enabled.data
        user.admin = form.admin.data
        

        db.session.add(user)
        db.session.commit()
        
        if notify_user:
            send_email(
                "Rhytmic Exam - User Registration Confirmed",
                sender="rhytmic.exam@gmail.com",
                recipients=[user.email],
                text_body=render_template("email/registration_complete.txt", user=user),
                html_body=render_template("email/registration_complete.html", user=user)
            )

        flash("User updated successfully", "success")

        return redirect(url_for("main.user_admin"))

    form.username.data = user.username
    form.name.data = user.name
    form.surname.data = user.surname
    form.sagf_id.data = user.sagf_id
    form.email.data = user.email
    form.enabled.data = user.enabled
    form.admin.data = user.admin
    
    return render_template("exam/update_user.html", title="Edit User", form=form, the_user=user.name)

@bp.route("/delete_user/<int:id>", methods=("POST",))
@login_required
@admin_required
def delete_user(id):
    user = User.query.filter_by(id=id).first_or_404()

    if user.username == current_user.username:
        flash("You cannot delete yourself", "danger")
        return redirect(url_for("main.user_admin"))
    else:
        db.session.delete(user)
        db.session.commit()
        
        flash(f"{user.username} has been deleted", "success")
        return redirect(url_for("main.user_admin"))

@bp.route("/dashboard")
@login_required
def dashboard():        

    exam_results = ExamResult.query.filter_by(sagf_id=current_user.sagf_id).first()

    return render_template("dashboard.html", title="Dashboard", exam_result=exam_results)

@bp.route("/edit_questions")
@login_required
@admin_required
def edit_questions():
    page = request.args.get("page", 1, type=int)

    question_pages = ExamQuestions.query.paginate(page=page , per_page=8)
    
    return render_template(
        "exam/edit_questions.html",
        title="Edit Questions",
        questions=question_pages)

@bp.route("/edit_exam_question/<int:question_id>", methods=("GET", "POST"))
@login_required
@admin_required
def edit_exam_question(question_id):
    # This is still super sketchy. I'm allowing html tags as input, but there
    # is nothing stopping the user to input malicious scripts as well
    # Obviously, don't use this in production
    exam_question = ExamQuestions.query.filter_by(question_id=question_id).first_or_404()

    form = AddExamQuestionsForm()

    if form.validate_on_submit():
        question_text = form.question.data or ""
        exam_question.question = question_text
        if "<block>" in question_text:
            exam_question.question = _formatblock(question_text)
        exam_question.question_images = form.question_images.data
        exam_question.question_type = form.question_type.data
        exam_question.option_a = form.option_a.data
        exam_question.option_b = form.option_b.data
        exam_question.option_c = form.option_c.data
        exam_question.option_d = form.option_d.data
        exam_question.answer = form.answer.data
        exam_question.exam_level = form.exam_level.data
        exam_question.question_category = form.question_category.data

        db.session.add(exam_question)
        db.session.commit()

        flash(f"Question {question_id} updated successfully", "success")
        return redirect(url_for("main.edit_questions"))

    form.question.data = exam_question.question
    form.question_type.data = exam_question.question_type
    form.question_images.data = exam_question.question_images
    form.option_a.data = exam_question.option_a
    form.option_b.data = exam_question.option_b
    form.option_c.data = exam_question.option_c
    form.option_d.data = exam_question.option_d
    form.question_category.data = exam_question.question_category
    
    return render_template("exam/edit_exam_question.html", title="Edit Exam Quesitons", question_id=exam_question.question_id, form=form)

@bp.route("/add_question", methods=("GET", "POST"))
@login_required
@admin_required
def add_question():
    form = AddExamQuestionsForm()

    if form.validate_on_submit():
        next_question_id = (db.session.query(db.func.max(ExamQuestions.question_id)).scalar() or 0) + 1

        q = ExamQuestions()
        q.question_id = next_question_id
        q.question = form.question.data
        q.question_type = form.question_type.data
        q.question_images = form.question_images.data
        q.option_a = form.option_a.data
        q.option_b = form.option_b.data
        q.option_c = form.option_c.data
        q.option_d = form.option_d.data
        q.answer = form.answer.data
        q.exam_level = form.exam_level.data
        q.question_category = form.question_category.data

        db.session.add(q)
        db.session.commit()

        flash("Question successfully added", "success")
        return redirect(url_for("main.add_question"))
    
    return render_template("exam/add_question.html", title="Add Exam Question", form=form)

@bp.route("/delete_question/<int:question_id>", methods=("POST",))
@login_required
@admin_required
def delete_question(question_id):
    ExamQuestions.query.filter_by(question_id=question_id).delete()

    db.session.commit()

    flash(f"Question number {question_id} deleted", "success")
    
    return redirect(url_for("main.edit_questions"))

@bp.route("/disclaimer", methods=("GET", "POST"))
def disclaimer():
    """ 
        The user must agree (and mostly be aware) that they will have a limited
        time to complete the theory and practical exam

        THIS DOES NOT WORK YET
    """
    prev_page = request.cookies.get("previous_page")
    form = Disclaimer()

    if request.method == "POST":
        flash("redirected")
        #go back to the caller
        agreed = request.form.get("invalidCheck")
        return redirect("main.index")

    resp = make_response(render_template("exam/disclaimer.html", form=form))
    resp.set_cookie("previous_page", request.referrer)

    return resp

@bp.route("/practical_exam", methods=("GET", "POST"))
@login_required
def practical_exam():

    if current_user.answers and current_user.answers[0].practical_taken:
        flash("You have already taken the practical exam", "info")
        return redirect(url_for("main.dashboard"))

    practical_questions = ExamQuestions.query.filter_by(question_category="practical")
    
    practical_progress = ExamResult.query.filter_by(sagf_id=current_user.sagf_id).first()
    if not practical_progress and not current_user.is_admin:
        #The user has not taken the theory yet
        flash("The Theory Exam must be taken first", "info")
        return(redirect(url_for("main.dashboard")))

    # Admins can preview practical flow without persisted progress.
    if not practical_progress and current_user.is_admin:
        practical_progress = ExamResult()

    if practical_progress is None:
        flash("Unable to initialize practical exam progress", "danger")
        return redirect(url_for("main.dashboard"))

    x = 1

    q_dict = {
        "questions":[],
        "videos":[],
        "heading":[],
    }

    for question in practical_questions:
        q_dict["questions"].append(json.loads(question.question)["question"])
        q_dict["heading"].append(json.loads(question.question)["heading"])
        #find a better way to do this... .loading the same data over and over again here
        q_dict["videos"] = [vid for vid in json.loads(question.question_images)["videos"]]
        x += 1

    progress = {"q_id":0, "v_id":0, "answered":0}
    if current_user.answers and current_user.answers[0].practical_progress is not None:
        progress = json.loads(current_user.answers[0].practical_progress)

    if request.method == "POST":
        form_result = request.form.to_dict()
        #Do some work to update the db with the progress
        if progress["v_id"] == 4:
            progress["v_id"] = 0
            progress["q_id"] += 1
        else:
            progress["v_id"] += 1
        #How many question have been answered
        progress["answered"] += 1

        practical_progress.practical_progress = json.dumps(progress)

        current_app.logger.info("%s has progressed in practical to %s", current_user.name, progress)

        if practical_progress.practical_answer is None:
            practical_progress.practical_answer = json.dumps({f"answer_{progress['answered']}": form_result.get("answer")})
        else:
            answered_sofar = json.loads(practical_progress.practical_answer)
            answered_sofar[f"answer_{progress['answered']}"] = form_result.get("answer")
            #update the databse value
            practical_progress.practical_answer = json.dumps(answered_sofar)

        if progress["answered"] == 20:
            practical_progress.practical_taken = True
            practical_progress.exam_end_date = datetime.datetime.today()

            if not current_user.is_admin:
                db.session.add(practical_progress)
                db.session.commit()

            flash("Practical Exam completed. Good luck!", "success")
            return redirect(url_for("main.dashboard"))

        if not current_user.is_admin:
            db.session.add(practical_progress)
            db.session.commit()

        return render_template("exam/practical_exam.html", title="National Practical Exam", q_dict=q_dict, progress=progress)
       
    return render_template("exam/practical_exam.html", title="National Practical Exam", q_dict=q_dict, progress=progress)
    
@bp.route("/theory_exam", methods=("GET", "POST"))
@login_required
def theory_exam():
    #set a cookie in the browser that will disable rendering the page in case a 
    #user deciceds to reload the page - which they shouldn't
    theory_exam_started = int(request.cookies.get("theory_loaded", 0))

    if current_user.is_admin:
        #bypas check for admin
        theory_exam_started = 0

    if theory_exam_started == 1:
        flash("You have already attempted the theory exam but did not complete it. You cannot retry the exam", "danger")
        current_app.logger.warn("%s attempted re-entry into theory exam", current_user.name)
        return redirect(url_for("main.dashboard"))

    user = User.query.filter_by(id = current_user.id).first_or_404()
    if not current_user.is_admin:
        #check if the current user has already taken the theory exam
        if user.answers and user.answers[0].theory_taken:
            flash("You have already completed the theory exam", "info")
            return redirect(url_for("main.dashboard"))
    
    current_app.logger.info("%s Theory called", current_user.name)

    if request.method == "POST" and request.endpoint == "main.theory_exam":
        if not current_user.is_admin:
            answers = request.form.to_dict()
            if "btnsubmit" in answers: 
                del answers["btnsubmit"]
            result = ExamResult()
            result.theory_answer = json.dumps(answers)
            result.theory_taken = True
            result.exam_start_date = datetime.datetime.today()
            result.sagf_id = user.sagf_id
            
            db.session.add(result)
            db.session.commit()
        else:
            flash("You are an admin user. Results will not be saved to the database", "info")

        flash("Theory Exam completed. Good Luck!", "success")
        return(redirect(url_for("main.dashboard")))

    question_list = []
    if current_user.is_admin or not current_user.level:
        #Get everything
        exam_questions = ExamQuestions.query.filter_by(question_category="theory")
    else:
        if current_user.level == "2":
            exam_questions = ExamQuestions.query.filter(
                and_(
                    ExamQuestions.question_category=="theory",
                    ExamQuestions.exam_level.in_(["1","2"])
                )
            )
        else:
            exam_questions = ExamQuestions.query.filter(
                and_(
                    ExamQuestions.question_category=="theory",
                    ExamQuestions.exam_level==current_user.level
                    )
                )

    for exam_question in exam_questions:
        question_list.append(make_question_for_exam(exam_question,exam_question.question_type))

    resp = make_response(render_template("exam/theory_exam.html", title="National Theory Exam", questions=question_list))

    #set the cookie that will expire
    resp.set_cookie(
        "theory_loaded",
        "1",
        expires=datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        )

    return resp

@bp.route("/results")
@login_required
@admin_required
def results():
    """ Display a list of all the entrants results """
    #answers shouldn't really be part of the exam_result table. fix this
    exam_answers = {}
    exam_practical_answers = {}

    #  exam_questions = ExamQuestions.query.filter(
    #         and_(
    #             ExamQuestions.question_category=="theory",
    #             ExamQuestions.exam_level==current_user.level
    #             )
    #         )
    
    theory_answers = ExamQuestions.query.filter_by(question_category="theory")
    # theory_answers = ExamQuestions.query.filter_by(question_category="theory").all()
    practical_answers = ExamPractialAnswers.query.all()
    
    for theory_answer in theory_answers:
        exam_answers[f"{theory_answer.question_id}"] = {
            "answer":theory_answer.answer,
            "level":theory_answer.exam_level
        }

    for practical_answer in practical_answers:
        exam_practical_answers[f"{practical_answer.id}"] = practical_answer.control_score

    exam_result = []
    participants = [x.sagf_id for x in User.query.filter(User.level.in_(["1","2"]))]
    results = ExamResult.query.filter(ExamResult.sagf_id.in_(participants))
    for result in results:
        r = {}
        r["name"] = f"{result.linked_user.name} {result.linked_user.surname}"
        r["sagf_id"] = result.linked_user.sagf_id
        #Filter bases on level
        exam_answer_copy = {}
        for k,v in exam_answers.items():
            if v["level"] == result.linked_user.level:
                exam_answer_copy[k] = v["answer"]
        #calculate the theory result
        percent, missed = calculate_theory_score(json.loads(result.theory_answer), exam_answer_copy)
        r["theory"] = percent
        r["theory_missed"] = missed
        #practical answer cannot be None 
        if not result.practical_answer: result.practical_answer = '{"answer_1":"0"}'
        practical_percent, practical_calculated_answer = calculate_practical_score(json.loads(result.practical_answer), practical_answers)
        r["practical"] = practical_percent
        r["practical_answers"] = practical_calculated_answer
        r["level"] = result.linked_user.level
        date_taken = result.exam_start_date
        date_diff = datetime.datetime.today()-date_taken
        if date_diff.days <= 2:
            r["recent"] = "1"
        else:
            r["recent"] = "-1"

        exam_result.append(r)

    return render_template("exam/results.html", title="Exam Results", exam_result=exam_result)

@bp.route('/download_results', methods=("GET",))
def download_results():

    csv_out = []

    # This isn't right. we should rather filter on recent results   
    participants = [x.sagf_id for x in User.query.filter(User.level.in_(["1","2"]))]
    results = ExamResult.query.filter(ExamResult.sagf_id.in_(participants))
    # results = ExamResult.query.all()
    practical_answers = ExamPractialAnswers.query.all()
    theory_answers = ExamQuestions.query.filter(
        and_(
            ExamQuestions.question_category=="theory",
            ExamQuestions.exam_level.in_(["1", "2"])
        )
    )

    for result in results:
        t_answers = {}
        csv_out.append([result.linked_user.name, result.linked_user.surname, result.linked_user.sagf_id])
        for theory_answer in theory_answers:
            if theory_answer.exam_level == result.linked_user.level:
                t_answers[f"{theory_answer.question_id}"] = theory_answer.answer
                
        theory_percent, theory_missed = calculate_theory_score(json.loads(result.theory_answer), t_answers)
        # practical_percent, practical_calculated_answer = calculate_practical_score(json.loads(result.practical_answer), practical_answers)
        csv_out.append(["Theory", f"{theory_percent}%"])
        # csv_out.append(["Apparatus", "D12", "Mark", "D34", "Mark", "AV", "Mark", "EX", "Mark"])
        # for app in practical_calculated_answer.keys():
        #     app_scores = []
        #     d12 = practical_calculated_answer.get(app).get("D1 + D2")
        #     d34 = practical_calculated_answer.get(app).get("D3 + D4")
        #     av = practical_calculated_answer.get(app).get("AV")
        #     ex = practical_calculated_answer.get(app).get("EX")

        #     app_scores = [app, f"({d12[0]}) {d12[1]}", d12[2], f"({d34[0]}) {d34[1]}", d34[2], f"({av[0]}) {av[1]}", av[2], f"({ex[0]}) {ex[1]}", ex[2]] 
        #     csv_out.append(app_scores)
        
        csv_out.append(["",""])
        csv_out.append(["Missed Theory", theory_missed])
        csv_out.append(["",""])
    
    si = StringIO()

    cw = csv.writer(si)
    cw.writerows(csv_out)

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=exam_result.csv"
    output.headers["Content-type"] = "text/csv"

    current_app.logger.info("%s requested file download", current_user.name)
    return output

def _formatblock(s:str) -> str:
    # if we encounter '<block>' in the text
    # then remove it and replace it
    # making it pretty
    block_start = "<block>"
    tag_len = len(block_start)
    end_of_block = "</block>"
    replacement_string = """<div class="panel panel-default">
                                <div class="panel-body">
                                    *
                                </div>
                            </div>"""
    # find where the block begins
    from_here = s.index(block_start) + tag_len
    modified = s[from_here:].replace(end_of_block,"")

    s = s[:s.index(block_start)] + replacement_string.replace("*", modified)

    return s