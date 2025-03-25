import os


def create_structure():
    base_dir = "smart_attendance"
    templates_dir = os.path.join(base_dir, "templates")
    
    # Define the file paths to create
    file_paths = [
        os.path.join(templates_dir, "unified_login.html"),
        os.path.join(templates_dir, "lecturer_dashboard.html"),
        os.path.join(templates_dir, "student_dashboard.html"),
        os.path.join(base_dir, "app.py"),
        os.path.join(base_dir, "student_database.json"),
        os.path.join(base_dir, "lecturer_database.json")
    ]
    
    # Create directories
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create each file if it does not exist
    for file_path in file_paths:
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                pass  # Creates an empty file
    
    print("Project structure created successfully.")


if __name__ == "__main__":
    create_structure()
