import json
import os

DATABASE_FILE = os.path.join("smart_attendance", "lecturer_database.json")


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


def add_lecturer(database):
    print("Enter the lecturer details. Leave blank at any prompt to cancel.")

    unique_id = input("Unique ID (e.g., lecturer1): ").strip()
    if not unique_id:
        print("No Unique ID provided. Cancelling...")
        return None

    if unique_id in database:
        print(f"Unique ID '{unique_id}' is already registered. Please use a different Unique ID.")
        return None

    name = input("Name (e.g., Lusimbo): ").strip()
    if not name:
        print("No Name provided. Cancelling...")
        return None

    email = input("Email (e.g., lusimbo@university.edu): ").strip()
    if not email:
        print("No Email provided. Cancelling...")
        return None

    password = input("Password (e.g., lecpass1): ").strip()
    if not password:
        print("No Password provided. Cancelling...")
        return None

    lecturer = {
        "password": password,
        "unique_id": unique_id,
        "name": name,
        "email": email
    }

    return unique_id, lecturer


def main():
    database = load_database()
    while True:
        print("\n--- Add a new lecturer ---")
        result = add_lecturer(database)
        if result is not None:
            unique_id, lecturer = result
            database[unique_id] = lecturer
            save_database(database)
            print(f"Lecturer with Unique ID '{unique_id}' added successfully.")

        cont = input("Do you want to add another lecturer? (y/n): ").strip().lower()
        if cont != "y":
            print("Exiting.")
            break


if __name__ == "__main__":
    main()
