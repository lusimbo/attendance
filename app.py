from flask import Flask, request, session, redirect, url_for, render_template, flash, send_file, get_flashed_messages, jsonify
import random
import datetime
import json
import io
import csv
from threading import Timer
import math
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key in production

# Dummy lecturer location (set by lecturer, hidden from students)
LECTURER_LOCATION = None
ALLOWED_DISTANCE_KM = 0.5
MIN_IDENTITY_SCORE = 0.9

# Track devices that have been used
used_devices = {}

# Auto-check settings
AUTO_CHECK_INTERVAL = None  # In minutes, set by lecturer
AUTO_CHECK_TIMER = None
SESSION_DURATION = None  # In hours, set by lecturer
SESSION_END_TIME = None  # Calculated based on start time + duration
LIVE_MONITORING_UPDATES = []  # Store live monitoring messages


# Load databases from JSON files with absolute paths
def load_students():
    try:
        with open('C:/Users/Lusimbo/Desktop/attend/smart_attendance/student_database.json', 'r') as f:
            data = json.load(f)
            print("Loaded students:", data)
            return data
    except FileNotFoundError:
        print("Student database file not found.")
        return {}


def load_lecturers():
    try:
        with open('C:/Users/Lusimbo/Desktop/attend/smart_attendance/lecturer_database.json', 'r') as f:
            data = json.load(f)
            print("Loaded lecturers:", data)
            return data
    except FileNotFoundError:
        print("Lecturer database file not found.")
        return {}


# Save databases to JSON files
def save_students(users):
    with open('C:/Users/Lusimbo/Desktop/attend/smart_attendance/student_database.json', 'w') as f:
        json.dump(users, f, indent=4)


def save_lecturers(lecturers):
    with open('C:/Users/Lusimbo/Desktop/attend/smart_attendance/lecturer_database.json', 'w') as f:
        json.dump(lecturers, f, indent=4)


# Initialize data
users = load_students()
lecturers = load_lecturers()
attendance_data = []
notifications = {}
student_notifications = {}

# Global variables
current_attendance_code = None
attendance_start_time = None


# Haversine formula to calculate distance between two coordinates (in kilometers)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


# Function to check response timeout
def check_response_timeout(student_id, notification_id):
    if notification_id in notifications and notifications[notification_id]['student_id'] == student_id:
        if not notifications[notification_id]['responded']:
            for record in attendance_data:
                if record['user'] == student_id and record['status'] == 'present':
                    record['status'] = 'left_early'
                    record['check_out_time'] = datetime.datetime.now()
                    record['time_spent'] = (record['check_out_time'] - record['time']).total_seconds() / 60
                    record['location_check'] = f"Out of Required Location (Lat: {record['current_latitude']}, Lon: {record['current_longitude']})"
                    break
            del notifications[notification_id]
            save_students(users)


# Auto-check function to verify student presence
def auto_check_presence():
    global LECTURER_LOCATION, AUTO_CHECK_INTERVAL, AUTO_CHECK_TIMER, SESSION_END_TIME, LIVE_MONITORING_UPDATES
    if not LECTURER_LOCATION or not AUTO_CHECK_INTERVAL or not SESSION_END_TIME:
        print("Auto-check skipped: Location, interval, or session end time not set.")
        return

    current_time = datetime.datetime.now()
    if current_time >= SESSION_END_TIME:
        print("Session ended. Stopping auto-check.")
        if AUTO_CHECK_TIMER:
            AUTO_CHECK_TIMER.cancel()
        LIVE_MONITORING_UPDATES.append(f"Session ended at {current_time.strftime('%H:%M:%S')}. Auto-check stopped.")
        return

    present_students = [record for record in attendance_data if record['status'] == 'present']
    if not present_students:
        print("Auto-check: No present students to check.")
        LIVE_MONITORING_UPDATES.append(f"{current_time.strftime('%H:%M:%S')}: No present students to check.")
    else:
        print(f"Auto-checking {len(present_students)} students at {current_time}")
        update_message = f"{current_time.strftime('%H:%M:%S')}: Checked {len(present_students)} students - "
        for record in present_students:
            student_id = record['user']
            current_lat = record.get('current_latitude', record['latitude'])
            current_lon = record.get('current_longitude', record['longitude'])
            distance = calculate_distance(
                current_lat, current_lon,
                LECTURER_LOCATION['latitude'], LECTURER_LOCATION['longitude']
            )

            if distance > ALLOWED_DISTANCE_KM:
                record['status'] = 'left_early'
                record['check_out_time'] = datetime.datetime.now()
                record['time_spent'] = (record['check_out_time'] - record['time']).total_seconds() / 60
                record['location_check'] = f"Out of Required Location (Lat: {current_lat}, Lon: {current_lon})"
                flash(f"Student {users[student_id]['name']} ({student_id}) left early. Time spent: {record['time_spent']:.1f} minutes.")
                print(f"Student {student_id} marked as left_early. Distance: {distance:.2f} km, Time spent: {record['time_spent']:.1f} minutes")
                update_message += f"{student_id} (Left), "
                # Send notification to student
                if student_id not in student_notifications:
                    student_notifications[student_id] = []
                student_notifications[student_id].append({
                    'message': f"You left the meeting early. Time spent: {record['time_spent']:.1f} minutes.",
                    'timestamp': datetime.datetime.now().isoformat(),
                    'read': False
                })
            else:
                record['location_check'] = "Still in Location"
                flash(f"Student {users[student_id]['name']} ({student_id}) still active at location.")
                print(f"Student {student_id} still active. Distance: {distance:.2f} km")
                update_message += f"{student_id} (Active), "

        LIVE_MONITORING_UPDATES.append(update_message.rstrip(", "))

    save_students(users)

    # Reschedule the next check if session hasn't ended
    AUTO_CHECK_TIMER = Timer(AUTO_CHECK_INTERVAL * 60, auto_check_presence)
    AUTO_CHECK_TIMER.start()


# Unified Login Page
@app.route('/', methods=['GET'])
def unified_login():
    return render_template('unified_login.html')


# Student Login Handler
@app.route('/student_login', methods=['POST'])
def student_login():
    unique_id = request.form.get('unique_id')
    password = request.form.get('password')
    print(f"Student login attempt - Unique ID: '{unique_id}', Password: '{password}'")
    user = users.get(unique_id)
    print(f"Retrieved student: {user}")
    if user and user['password'] == password:
        print("Student login successful")
        session['user'] = unique_id
        return redirect(url_for('student_dashboard'))
    print("Student login failed: Invalid credentials")
    return "Invalid student credentials. Please try again."


# Lecturer Login Handler
@app.route('/lecturer_login', methods=['POST'])
def lecturer_login():
    unique_id = request.form.get('unique_id')
    password = request.form.get('password')
    print(f"Lecturer login attempt - Unique ID: '{unique_id}', Password: '{password}'")
    lecturer = lecturers.get(unique_id)
    print(f"Retrieved lecturer: {lecturer}")
    if lecturer:
        print(f"Comparing passwords: Stored='{lecturer['password']}', Entered='{password}'")
        if lecturer['password'] == password:
            print("Lecturer login successful")
            session['lecturer'] = unique_id
            return redirect(url_for('lecturer_dashboard'))
        else:
            print("Password mismatch")
    else:
        print(f"No lecturer found with unique_id: {unique_id}")
    print("Lecturer login failed: Invalid credentials")
    return "Invalid lecturer credentials. Please try again."


# Lecturer Dashboard
@app.route('/lecturer_dashboard', methods=['GET', 'POST'])
def lecturer_dashboard():
    if 'lecturer' not in session:
        return redirect(url_for('unified_login'))
    
    lecturer = lecturers.get(session['lecturer'])
    if not lecturer:
        return "Lecturer not found", 404
    
    global LECTURER_LOCATION, AUTO_CHECK_INTERVAL, AUTO_CHECK_TIMER, SESSION_DURATION, SESSION_END_TIME, attendance_start_time, LIVE_MONITORING_UPDATES
    lecturer_name = lecturer['name']
    lecturer_email = f"{lecturer_name.lower().replace(' ', '.')}.{session['lecturer']}@university.edu"
    code = current_attendance_code if current_attendance_code else "Not Generated"
    
    # Handle location setting
    if request.method == 'POST' and 'set_location' in request.form:
        latitude = float(request.form.get('latitude', 0))
        longitude = float(request.form.get('longitude', 0))
        LECTURER_LOCATION = {"latitude": latitude, "longitude": longitude}
        flash(f"Location set to Lat: {latitude}, Lon: {longitude}")

    # Handle auto-check and session duration settings
    if request.method == 'POST' and 'set_session' in request.form:
        interval = int(request.form.get('auto_check_interval', 2))
        duration = float(request.form.get('session_duration', 2))  # In hours
        AUTO_CHECK_INTERVAL = interval
        SESSION_DURATION = duration
        attendance_start_time = datetime.datetime.now()
        SESSION_END_TIME = attendance_start_time + datetime.timedelta(hours=SESSION_DURATION)
        LIVE_MONITORING_UPDATES = []  # Reset live monitoring updates
        flash(f"Session set: Auto-check every {interval} minutes for {duration} hours. Ends at {SESSION_END_TIME.strftime('%H:%M:%S')}")

        # Cancel existing timer if running
        if AUTO_CHECK_TIMER and AUTO_CHECK_TIMER.is_alive():
            AUTO_CHECK_TIMER.cancel()
        
        # Start new auto-check timer
        AUTO_CHECK_TIMER = Timer(AUTO_CHECK_INTERVAL * 60, auto_check_presence)
        AUTO_CHECK_TIMER.start()

    # Sort attendance_data by time in descending order (latest first)
    sorted_attendance_data = sorted(attendance_data, key=lambda x: x['time'], reverse=True)
    
    attendance_records = ""
    for record in sorted_attendance_data:
        status_color = "text-green-500" if record["status"] == "present" else "text-red-500"
        check_out = "Still Active" if record["status"] == "present" else "Left"
        time_spent = f"{record.get('time_spent', 0):.1f} min" if 'time_spent' in record else "N/A"
        location_check = record.get('location_check', "Still in Location")
        attendance_records += f"""
            <tr>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">{users[record['user']]['name']}</td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">{record['user']}</td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">{record['time'].strftime('%H:%M:%S')}</td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">Lat: {record['latitude']}, Lon: {record['longitude']}</td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700"><span class="{status_color}">{check_out}</span></td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">{time_spent}</td>
                <td class="py-2 px-4 border-b border-gray-300 dark:border-gray-700">{location_check}</td>
            </tr>
        """

    return render_template('lecturer_dashboard.html', lecturer_name=lecturer_name, lecturer_email=lecturer_email,
                          code=code, attendance_records=attendance_records, lecturer_location=LECTURER_LOCATION,
                          auto_check_interval=AUTO_CHECK_INTERVAL, session_duration=SESSION_DURATION,
                          session_end_time=SESSION_END_TIME, live_monitoring_updates=LIVE_MONITORING_UPDATES)


# Student Dashboard
@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if 'user' not in session:
        return redirect(url_for('unified_login'))
    
    user = users.get(session['user'])
    if not user:
        return "Student not found", 404
    
    student_name = user['name']
    reg_number = user['reg_number']
    course = user['course']
    
    # Handle location update
    if request.method == 'POST' and 'update_location' in request.form:
        latitude = float(request.form.get('latitude', 0))
        longitude = float(request.form.get('longitude', 0))
        for record in attendance_data:
            if record['user'] == session['user'] and record['status'] == 'present':
                record['current_latitude'] = latitude
                record['current_longitude'] = longitude
                flash(f"Location updated to Lat: {latitude}, Lon: {longitude}")
                # Trigger immediate auto-check
                auto_check_presence()
                break
    
    attendance_history = ""
    if user['last_attendance']:
        last_attendance = datetime.datetime.fromisoformat(user['last_attendance'])
        status = "✅ Present" if last_attendance else "❌ Absent"
        status_color = "text-green-500" if last_attendance else "text-red-500"
        attendance_history += f"""
            <tr>
                <td class="py-2 px-4 border-b">{last_attendance.strftime('%Y-%m-%d')}</td>
                <td class="py-2 px-4 border-b">{course.split()[0]}</td>
                <td class="py-2 px-4 border-b">Morning</td>
                <td class="py-2 px-4 border-b {status_color}">{status}</td>
            </tr>
        """
    else:
        attendance_history = "<tr><td colspan='4' class='py-2 px-4 text-center'>No attendance records yet.</td></tr>"

    # Check for active notifications (live check-in)
    active_notification = None
    for notif_id, notif in notifications.items():
        if notif['student_id'] == session['user'] and not notif['responded']:
            active_notification = notif_id
            break

    # Prepare student notifications
    student_notifs = student_notifications.get(session['user'], [])
    unread_count = sum(1 for notif in student_notifs if not notif['read'])

    return render_template('student_dashboard.html', student_name=student_name, reg_number=reg_number, course=course,
                          attendance_history=attendance_history, last_attendance=user['last_attendance'],
                          active_notification=active_notification, notifications=student_notifs, unread_count=unread_count)


# Route to generate attendance code
@app.route('/generate_code', methods=['GET'])
def generate_code():
    if 'lecturer' not in session:
        return redirect(url_for('unified_login'))
    
    global current_attendance_code, attendance_start_time
    current_attendance_code = str(random.randint(1000, 9999))
    attendance_start_time = datetime.datetime.now()
    
    flash(f"New attendance code generated: {current_attendance_code}. Share this with students.")
    
    return redirect(url_for('lecturer_dashboard'))


# Student Attendance Route
@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if 'user' not in session:
        return redirect(url_for('unified_login'))
    
    global current_attendance_code, LECTURER_LOCATION
    if request.method == 'POST':
        code_entered = request.form.get('attendance_code')
        latitude = float(request.form.get('latitude', 0))
        longitude = float(request.form.get('longitude', 0))
        device_id = request.form.get('device_id')
        identity_score = float(request.form.get('identity_score', 0))

        # Initialize check results
        checks_passed = True
        message = "Attendance Check Results:\n"

        # Check attendance code
        if code_entered != current_attendance_code:
            flash("Invalid attendance code. Please try again.")
            return redirect(url_for('student_dashboard'))

        # Check if lecturer location is set
        if not LECTURER_LOCATION:
            flash("Attendance declined: Lecturer location not set.")
            return redirect(url_for('student_dashboard'))

        # Location Check
        distance = calculate_distance(
            latitude, longitude,
            LECTURER_LOCATION['latitude'], LECTURER_LOCATION['longitude']
        )
        location_pass = distance <= ALLOWED_DISTANCE_KM
        location_status = "✅" if location_pass else "❌"
        message += f"📍 Location: {location_status} ({distance:.2f} km away)\n"
        if not location_pass:
            checks_passed = False

        # Device Check
        if device_id in used_devices:
            if used_devices[device_id] != session['user']:
                device_pass = False
                device_status = "❌"
                message += f"📱 Device: {device_status} (Device already used by another student)\n"
                checks_passed = False
            else:
                device_pass = True
                device_status = "✅"
                message += f"📱 Device: {device_status} (Device already registered to you)\n"
        else:
            device_pass = True
            device_status = "✅"
            message += f"📱 Device: {device_status} (New device registered)\n"
            used_devices[device_id] = session['user']

        # Identity Check
        identity_pass = identity_score >= MIN_IDENTITY_SCORE
        identity_status = "✅" if identity_pass else "❌"
        message += f"🔑 Identity: {identity_status} (Score: {identity_score:.2f})\n"
        if not identity_pass:
            checks_passed = False

        # Final decision
        if checks_passed:
            timestamp = datetime.datetime.now()
            attendance_data.append({
                "user": session['user'],
                "time": timestamp,
                "status": "present",
                "latitude": latitude,  # Original sign-in location
                "longitude": longitude,
                "current_latitude": latitude,  # Current location (updates later)
                "current_longitude": longitude,
                "device_id": device_id,
                "identity_score": identity_score,
                "location_check": "Still in Location"
            })
            users[session['user']]['last_attendance'] = timestamp.isoformat()
            save_students(users)
            flash(f"{message}Attendance marked successfully!")
        else:
            flash(f"{message}Attendance declined due to failed checks.")

        return redirect(url_for('student_dashboard'))
    
    return redirect(url_for('student_dashboard'))


# Check Now Route (Manual Check)
@app.route('/check_now', methods=['GET'])
def check_now():
    if 'lecturer' not in session:
        return redirect(url_for('unified_login'))
    
    present_students = [record['user'] for record in attendance_data if record['status'] == 'present']
    if not present_students:
        flash("No students currently marked as present.")
        return redirect(url_for('lecturer_dashboard'))
    
    for student_id in present_students:
        notification_id = f"notif_{student_id}_{datetime.datetime.now().timestamp()}"
        notifications[notification_id] = {
            'student_id': student_id,
            'time_sent': datetime.datetime.now(),
            'responded': False
        }
        Timer(300, check_response_timeout, args=[student_id, notification_id]).start()
    
    flash(f"Check-in request sent to {len(present_students)} students.")
    return redirect(url_for('lecturer_dashboard'))


# Student Response Route
@app.route('/respond_check_in/<notification_id>', methods=['POST'])
def respond_check_in(notification_id):
    if 'user' not in session:
        return redirect(url_for('unified_login'))
    
    if notification_id in notifications and notifications[notification_id]['student_id'] == session['user']:
        response = request.form.get('response')
        if response == 'yes':
            notifications[notification_id]['responded'] = True
        elif response == 'no':
            for record in attendance_data:
                if record['user'] == session['user'] and record['status'] == 'present':
                    record['status'] = 'left_early'
                    record['check_out_time'] = datetime.datetime.now()
                    record['time_spent'] = (record['check_out_time'] - record['time']).total_seconds() / 60
                    record['location_check'] = f"Out of Required Location (Lat: {record['current_latitude']}, Lon: {record['current_longitude']})"
                    # Send notification
                    if session['user'] not in student_notifications:
                        student_notifications[session['user']] = []
                    student_notifications[session['user']].append({
                        'message': f"You left the meeting early. Time spent: {record['time_spent']:.1f} minutes.",
                        'timestamp': datetime.datetime.now().isoformat(),
                        'read': False
                    })
                    break
            notifications[notification_id]['responded'] = True
        del notifications[notification_id]
        save_students(users)
    
    return redirect(url_for('student_dashboard'))


# Export Attendance Route
@app.route('/export_attendance')
def export_attendance():
    if 'lecturer' not in session:
        return redirect(url_for('unified_login'))
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'ID', 'Time', 'Latitude', 'Longitude', 'Device ID', 'Identity Score', 'Status', 'Time Spent (min)'])
    for record in attendance_data:
        writer.writerow([
            users[record['user']]['name'],
            record['user'],
            record['time'].strftime('%Y-%m-%d %H:%M:%S'),
            record.get('latitude', 'N/A'),
            record.get('longitude', 'N/A'),
            record.get('device_id', 'N/A'),
            record.get('identity_score', 'N/A'),
            record['status'].capitalize(),
            record.get('time_spent', 'N/A')
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'attendance_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


# New endpoint for lecturer to get attendance data in real-time
@app.route('/attendance_data', methods=['GET'])
def attendance_data_endpoint():
    if 'lecturer' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Sort attendance_data by time in descending order for real-time updates
    sorted_attendance_data = sorted(attendance_data, key=lambda x: x['time'], reverse=True)
    
    records = []
    for record in sorted_attendance_data:
        check_out = "Still Active" if record["status"] == "present" else "Left"
        time_spent = f"{record.get('time_spent', 0):.1f} min" if 'time_spent' in record else "N/A"
        location_check = record.get('location_check', "Still in Location")
        records.append({
            "name": users[record['user']]['name'],
            "id": record['user'],
            "time": record['time'].strftime('%H:%M:%S'),
            "location": f"Lat: {record['latitude']}, Lon: {record['longitude']}",
            "check_out": check_out,
            "time_spent": time_spent,
            "location_check": location_check,
            "status_color": "text-green-500" if record["status"] == "present" else "text-red-500"
        })
    return jsonify({"attendance_records": records})


# New endpoint for student to get their status and notifications in real-time
@app.route('/student_status', methods=['GET'])
def student_status_endpoint():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = users.get(session['user'])
    status = "Not Marked"
    current_location = "N/A"
    location_check = "N/A"
    for record in attendance_data:
        if record['user'] == session['user']:
            status = "Still Active" if record['status'] == 'present' else "Left Early"
            current_location = f"Lat: {record['current_latitude']}, Lon: {record['current_longitude']}"
            location_check = record.get('location_check', "Still in Location")
            break
    
    active_notification = None
    for notif_id, notif in notifications.items():
        if notif['student_id'] == session['user'] and not notif['responded']:
            active_notification = notif_id
            break

    student_notifs = student_notifications.get(session['user'], [])
    unread_count = sum(1 for notif in student_notifs if not notif['read'])

    return jsonify({
        "status": status,
        "current_location": current_location,
        "location_check": location_check,
        "active_notification": active_notification,
        "notifications": student_notifs,
        "unread_count": unread_count
    })


# Route to mark notifications as read
@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    if 'user' not in session:
        return redirect(url_for('unified_login'))
    
    if session['user'] in student_notifications:
        for notif in student_notifications[session['user']]:
            notif['read'] = True
    return redirect(url_for('student_dashboard'))


# New endpoint for live monitoring updates
@app.route('/live_monitoring_updates', methods=['GET'])
def live_monitoring_updates_endpoint():
    if 'lecturer' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"updates": LIVE_MONITORING_UPDATES[-10:]})  # Return last 10 updates for brevity


# Logout Route
@app.route('/logout')
def logout():
    global AUTO_CHECK_TIMER
    if AUTO_CHECK_TIMER and AUTO_CHECK_TIMER.is_alive():
        AUTO_CHECK_TIMER.cancel()
    session.pop('user', None)
    session.pop('lecturer', None)
    return redirect(url_for('unified_login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
