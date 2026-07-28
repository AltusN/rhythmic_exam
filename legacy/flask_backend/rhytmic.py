from rhytmic_exam_app import create_app, db

from rhytmic_exam_app.models import User, ExamResult, ExamQuestions, ExamPractialAnswers

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        "db":db,
        "User":User,
        "ExamResult":ExamResult,
        "ExamQuestions":ExamQuestions,
        "ExamPracticalAnswers":ExamPractialAnswers
        }