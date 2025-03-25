from flask import Blueprint, request, render_template, flash, redirect, url_for
import json
import os

student_bp = Blueprint('student', __name__, template_folder='templates')

DATABASE_FILE = os.path.join("smart_attendance", "student_database.json")


def load_database():
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_database(data):
    with open(DATABASE_FILE, "w") as f:
        json.dump(data, f, indent=2)


@student_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        unique_id = request.form.get('unique_id', '').strip()
        name = request.form.get('name', '').strip()
        course = request.form.get('course', '').strip()

        if not unique_id or not name or not course:
            flash('All fields are required.', 'error')
            return redirect(url_for('student.add_student'))

        database = load_database()
        if unique_id in database:
            flash(f"Unique ID '{unique_id}' is already registered.", "error")
            return redirect(url_for('student.add_student'))

        # Auto-generate password and registration number based on unique_id.
        parts = unique_id.split(".")
        if len(parts) == 2:
            password = f"I21/{parts[0]}/{parts[1]}"
            reg_number = password
        else:
            password = f"I21/{unique_id}"
            reg_number = password

        student = {
            "password": password,
            "unique_id": unique_id,
            "name": name,
            "last_attendance": None,
            "reg_number": reg_number,
            "course": course
        }

        database[unique_id] = student
        save_database(database)
        flash(f"Student '{name}' added successfully!", "success")
        return redirect(url_for('student.add_student'))
    
    return render_template('add_student.html')
