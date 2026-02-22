from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portal.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

    db.init_app(app)
    login_manager.init_app(app)

    register_routes(app)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Initialize the database."""
        with app.app_context():
            db.drop_all()
            db.create_all()
        print("Initialized the database.")

    return app


################################
# Database models
################################


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student/instructor

    courses = db.relationship("Course", backref="instructor", lazy=True)
    enrollments = db.relationship("Enrollment", backref="student", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_instructor(self) -> bool:
        return self.role == "instructor"

    def is_student(self) -> bool:
        return self.role == "student"


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    instructor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    contents = db.relationship("Content", backref="course", lazy=True, cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", backref="course", lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", backref="course", lazy=True, cascade="all, delete-orphan")


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)


class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    content_type = db.Column(db.String(20), nullable=False)  # video/pdf/other
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("Question", backref="quiz", lazy=True, cascade="all, delete-orphan")
    attempts = db.relationship("Attempt", backref="quiz", lazy=True, cascade="all, delete-orphan")


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)

    choices = db.relationship("Choice", backref="question", lazy=True, cascade="all, delete-orphan")


class Choice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, nullable=True)

    answers = db.relationship("AttemptAnswer", backref="attempt", lazy=True, cascade="all, delete-orphan")


class AttemptAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempt.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    choice_id = db.Column(db.Integer, db.ForeignKey("choice.id"), nullable=False)

    choice = db.relationship("Choice")


################################
# Login manager
################################


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


################################
# Helpers
################################


def instructor_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_instructor():
            flash("Instructor access required.", "warning")
            return redirect(url_for("index"))
        return func(*args, **kwargs)

    return wrapper


################################
# Routes
################################


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        courses = Course.query.order_by(Course.created_at.desc()).limit(6).all()
        return render_template("index.html", courses=courses)
        
    @app.route("/about")
    def about():
        return render_template("about.html")

    # -------- Auth --------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "student")

            if not username or not email or not password:
                flash("All fields are required.", "danger")
                return redirect(url_for("register"))

            if User.query.filter((User.username == username) | (User.email == email)).first():
                flash("Username or email already exists.", "danger")
                return redirect(url_for("register"))

            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid username or password.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # -------- Dashboards --------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.is_instructor():
            courses = Course.query.filter_by(instructor_id=current_user.id).all()
            quizzes = Quiz.query.join(Course).filter(Course.instructor_id == current_user.id).all()
            return render_template("dashboard_instructor.html", courses=courses, quizzes=quizzes)
        else:
            enrollments = (
                Enrollment.query.filter_by(student_id=current_user.id)
                .join(Course)
                .order_by(Course.created_at.desc())
                .all()
            )
            attempts = Attempt.query.filter_by(student_id=current_user.id).all()
            return render_template("dashboard_student.html", enrollments=enrollments, attempts=attempts)

    # -------- Course management --------
    @app.route("/courses")
    @login_required
    def courses():
        if current_user.is_instructor():
            courses = Course.query.filter_by(instructor_id=current_user.id).all()
        else:
            courses = Course.query.order_by(Course.created_at.desc()).all()
        return render_template("courses.html", courses=courses)

    @app.route("/courses/create", methods=["GET", "POST"])
    @login_required
    @instructor_required
    def create_course():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            if not title:
                flash("Course title is required.", "danger")
                return redirect(url_for("create_course"))
            course = Course(title=title, description=description, instructor_id=current_user.id)
            db.session.add(course)
            db.session.commit()
            flash("Course created.", "success")
            return redirect(url_for("courses"))
        return render_template("create_course.html")

    @app.route("/courses/<int:course_id>")
    @login_required
    def course_detail(course_id: int):
        course = Course.query.get_or_404(course_id)
        enrolled = False
        if current_user.is_student():
            enrolled = (
                Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
                is not None
            )
        return render_template("course_detail.html", course=course, enrolled=enrolled)

    @app.route("/courses/<int:course_id>/enroll", methods=["POST"])
    @login_required
    def enroll_course(course_id: int):
        course = Course.query.get_or_404(course_id)
        if not current_user.is_student():
            flash("Only students can enroll in courses.", "warning")
            return redirect(url_for("course_detail", course_id=course.id))
        existing = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if existing:
            flash("You are already enrolled.", "info")
        else:
            enrollment = Enrollment(student_id=current_user.id, course_id=course.id)
            db.session.add(enrollment)
            db.session.commit()
            flash("Enrolled in course.", "success")
        return redirect(url_for("course_detail", course_id=course.id))

    @app.route("/courses/<int:course_id>/unenroll", methods=["POST"])
    @login_required
    def unenroll_course(course_id: int):
        """Allow a student to leave a course."""
        course = Course.query.get_or_404(course_id)
        if not current_user.is_student():
            flash("Only students can unenroll from courses.", "warning")
            return redirect(url_for("course_detail", course_id=course.id))

        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if not enrollment:
            flash("You are not enrolled in this course.", "info")
        else:
            db.session.delete(enrollment)
            db.session.commit()
            flash("You have been unenrolled from the course.", "success")

        return redirect(url_for("courses"))

    # -------- Content management --------
    @app.route("/courses/<int:course_id>/content/upload", methods=["GET", "POST"])
    @login_required
    @instructor_required
    def upload_content(course_id: int):
        course = Course.query.get_or_404(course_id)
        if course.instructor_id != current_user.id:
            flash("You are not the instructor for this course.", "danger")
            return redirect(url_for("courses"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            content_type = request.form.get("content_type", "other")
            file = request.files.get("file")

            if not title or not file:
                flash("Title and file are required.", "danger")
                return redirect(url_for("upload_content", course_id=course.id))

            filename = secure_filename(file.filename)
            if not filename:
                flash("Invalid file name.", "danger")
                return redirect(url_for("upload_content", course_id=course.id))

            save_path = UPLOAD_FOLDER / filename
            file.save(save_path)

            content = Content(
                course_id=course.id,
                title=title,
                description=description,
                content_type=content_type,
                file_path=filename,
            )
            db.session.add(content)
            db.session.commit()
            flash("Content uploaded.", "success")
            return redirect(url_for("course_detail", course_id=course.id))

        return render_template("upload_content.html", course=course)

    @app.route("/courses/<int:course_id>/delete", methods=["POST"])
    @login_required
    @instructor_required
    def delete_course(course_id: int):
        """Allow the course instructor to remove a course and its related data."""
        course = Course.query.get_or_404(course_id)
        if course.instructor_id != current_user.id:
            flash("You are not the instructor for this course.", "danger")
            return redirect(url_for("courses"))

        db.session.delete(course)
        db.session.commit()
        flash("Course deleted.", "info")
        return redirect(url_for("courses"))

    @app.route("/uploads/<path:filename>")
    @login_required
    def uploaded_file(filename: str):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

    @app.route("/content/<int:content_id>")
    @login_required
    def view_content(content_id: int):
        """Render a piece of course content inside the portal layout instead of a separate tab."""
        content = Content.query.get_or_404(content_id)
        course = content.course

        # Optionally, require enrollment for students
        if current_user.is_student():
            enrolled = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
            if not enrolled:
                flash("You must be enrolled in this course to view its content.", "warning")
                return redirect(url_for("course_detail", course_id=course.id))

        file_url = url_for("uploaded_file", filename=content.file_path)
        return render_template("view_content.html", content=content, course=course, file_url=file_url)

    # -------- Quiz management --------
    @app.route("/courses/<int:course_id>/quizzes/create", methods=["GET", "POST"])
    @login_required
    @instructor_required
    def create_quiz(course_id: int):
        course = Course.query.get_or_404(course_id)
        if course.instructor_id != current_user.id:
            flash("You are not the instructor for this course.", "danger")
            return redirect(url_for("courses"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if not title:
                flash("Quiz title is required.", "danger")
                return redirect(url_for("create_quiz", course_id=course.id))

            quiz = Quiz(course_id=course.id, title=title)
            db.session.add(quiz)
            db.session.flush()

            # Simple dynamic question parsing: q1_text, q1_choice1, q1_choice1_correct, ...
            index = 1
            while True:
                q_text = request.form.get(f"q{index}_text")
                if not q_text:
                    break
                question = Question(quiz_id=quiz.id, text=q_text.strip())
                db.session.add(question)
                db.session.flush()

                for c_index in range(1, 5):
                    c_text = request.form.get(f"q{index}_choice{c_index}")
                    if not c_text:
                        continue
                    is_correct = request.form.get(f"q{index}_correct") == str(c_index)
                    choice = Choice(question_id=question.id, text=c_text.strip(), is_correct=is_correct)
                    db.session.add(choice)

                index += 1

            db.session.commit()
            flash("Quiz created.", "success")
            return redirect(url_for("course_detail", course_id=course.id))

        return render_template("create_quiz.html", course=course)

    @app.route("/quizzes/<int:quiz_id>/take", methods=["GET", "POST"])
    @login_required
    def take_quiz(quiz_id: int):
        quiz = Quiz.query.get_or_404(quiz_id)
        if current_user.is_instructor():
            flash("Instructors cannot take quizzes.", "warning")
            return redirect(url_for("course_detail", course_id=quiz.course_id))

        if request.method == "POST":
            attempt = Attempt(quiz_id=quiz.id, student_id=current_user.id, started_at=datetime.utcnow())
            db.session.add(attempt)
            db.session.flush()

            correct_count = 0
            total_questions = len(quiz.questions)

            for question in quiz.questions:
                choice_id = request.form.get(f"question_{question.id}")
                if not choice_id:
                    continue
                choice = Choice.query.get(int(choice_id))
                if choice and choice.is_correct:
                    correct_count += 1
                answer = AttemptAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    choice_id=choice.id if choice else int(choice_id),
                )
                db.session.add(answer)

            score = (correct_count / total_questions) * 100 if total_questions else 0
            attempt.score = score
            attempt.completed_at = datetime.utcnow()
            db.session.commit()
            flash(f"Quiz submitted. Your score: {score:.1f}%", "info")
            return redirect(url_for("dashboard"))

        return render_template("take_quiz.html", quiz=quiz)

    @app.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
    @login_required
    @instructor_required
    def edit_quiz(quiz_id: int):
        """Allow the instructor to edit an existing quiz (title, questions, and correct answers)."""
        quiz = Quiz.query.get_or_404(quiz_id)
        if quiz.course.instructor_id != current_user.id:
            flash("You are not the instructor for this course.", "danger")
            return redirect(url_for("courses"))

        if request.method == "POST":
            new_title = request.form.get("title", "").strip()
            if new_title:
                quiz.title = new_title

            # Update questions and choices text + correct answers
            for question in quiz.questions:
                q_text = request.form.get(f"q{question.id}_text", "").strip()
                if q_text:
                    question.text = q_text

                correct_choice_id = request.form.get(f"q{question.id}_correct")

                for choice in question.choices:
                    c_text = request.form.get(f"choice{choice.id}_text", "").strip()
                    if c_text:
                        choice.text = c_text
                    choice.is_correct = bool(correct_choice_id and str(choice.id) == correct_choice_id)

            db.session.commit()
            flash("Quiz updated.", "success")
            return redirect(url_for("course_detail", course_id=quiz.course_id))

        return render_template("edit_quiz.html", quiz=quiz)

    @app.route("/attempts/<int:attempt_id>/result")
    @login_required
    def view_attempt_result(attempt_id: int):
        """Show detailed results for a quiz attempt, including correct answers."""
        attempt = Attempt.query.get_or_404(attempt_id)
        if current_user.is_instructor() or attempt.student_id != current_user.id:
            flash("You are not allowed to view this result.", "danger")
            return redirect(url_for("dashboard"))

        quiz = attempt.quiz
        # Map question_id -> AttemptAnswer for easier lookup in the template
        answers_by_q = {answer.question_id: answer for answer in attempt.answers}
        # Map question_id -> correct Choice for each question
        correct_by_question = {}
        student_choice_by_question = {}
        for q in quiz.questions:
            for c in q.choices:
                if c.is_correct:
                    correct_by_question[q.id] = c
                    break
            ans = answers_by_q.get(q.id)
            if ans:
                for c in q.choices:
                    if c.id == ans.choice_id:
                        student_choice_by_question[q.id] = c
                        break

        return render_template(
            "view_result.html",
            attempt=attempt,
            quiz=quiz,
            answers_by_q=answers_by_q,
            correct_by_question=correct_by_question,
            student_choice_by_question=student_choice_by_question,
        )


################################
# Application entry point
################################


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)

