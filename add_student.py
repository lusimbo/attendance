import json
import os

DATABASE_FILE = os.path.join("smart_attendance", "student_database.json")


def load_database():
    # Ensure the directory exists
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


def add_student(database):
    print("Enter the student details. Leave blank at any prompt to cancel.")

    unique_id = input("Unique ID (e.g., 6576.2021): ").strip()
    if not unique_id:
        print("No Unique ID provided. Cancelling...")
        return None

    if unique_id in database:
        print(f"Unique ID '{unique_id}' already registered. Please use a different Unique ID.")
        return None

    name = input("Name (e.g., Saning'o Totona): ").strip()
    if not name:
        print("No Name provided. Cancelling...")
        return None

    course = input("Course (e.g., Telecommunications and Information Technology): ").strip()
    if not course:
        print("No Course provided. Cancelling...")
        return None

    # Auto-generate password and registration number based on the unique_id.
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

    return unique_id, student


def main():
    database = load_database()
    while True:
        print("\n--- Add a new student ---")
        result = add_student(database)
        if result is not None:
            unique_id, student = result
            database[unique_id] = student
            save_database(database)
            print(f"Student with Unique ID '{unique_id}' added successfully.")

        cont = input("Do you want to add another student? (y/n): ").strip().lower()
        if cont != "y":
            print("Exiting.")
            break


if __name__ == "__main__":
    main()
