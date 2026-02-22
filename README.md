# Student E-Learning Management Portal

Python / Flask based E-Learning portal that supports:

- User authentication with **student** and **instructor** roles
- Course management for instructors
- Content management for video/PDF/other files
- Quiz and assessment creation + automatic scoring
- Dashboards for students and instructors with basic progress tracking

## Tech stack

- **Backend**: Python, Flask, Flask-SQLAlchemy, Flask-Login
- **Database**: SQLite (local `portal.db`)
- **Frontend**: HTML, CSS (simple blue color scheme), a bit of vanilla JS (via forms)

## Project structure

- `app.py` – Flask app, models, and routes
- `templates/` – HTML templates (Jinja2)
- `static/style.css` – global styles
- `uploads/` – uploaded files (created automatically at runtime)
- `requirements.txt` – Python dependencies

## Setup & run

From the `Student_Portel` folder:

```bash
python -m venv venv
venv\Scripts\activate  # on Windows
# source venv/bin/activate  # on macOS / Linux

pip install -r requirements.txt
```

Initialize the database (optional but recommended to reset cleanly):

```bash
flask --app app.py init-db
```

Run the development server:

```bash
python app.py
```

Then open `http://127.0.0.1:5000/` in your browser.

## Basic usage

- Register as **Instructor** to create courses, upload content, and build quizzes.
- Register as **Student** to enroll in courses, view materials, and take quizzes.
- Student dashboard shows:
  - Enrolled courses
  - Quiz attempts with scores (performance tracking)
- Instructor dashboard shows:
  - Created courses
  - Quizzes across their courses

