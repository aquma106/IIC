from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
from werkzeug.utils import secure_filename
import time

# ========================= APP SETUP =========================
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY")  # Change in production

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ========================= DATABASE CONNECTION =========================
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
def fetch_all(query, params=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

def execute_query(query, params=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    cursor.close()
    conn.close()

# ========================= CREATE TABLES & DEFAULT ADMIN =========================
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # Admin Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role VARCHAR(20) DEFAULT 'admin'
    )
    """)

    # Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_name VARCHAR(100) NOT NULL,
        description TEXT,
        date DATE,
        image VARCHAR(255)
    )
    """)

    # Gallery Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gallery (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(100),
        image VARCHAR(255) NOT NULL
    )
    """)

    # ✅ DEFAULT ADMIN
    default_user = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    default_pass = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

    cursor.execute("SELECT * FROM admin_users WHERE username = %s", (default_user,))
    if not cursor.fetchone():
        hashed = generate_password_hash(default_pass)
        cursor.execute(
            "INSERT INTO admin_users (username, password, role) VALUES (%s, %s, %s)",
            (default_user, hashed, "admin")
        )

    conn.commit()
    cursor.close()
    conn.close()

# ========================= ADMIN REQUIRED DECORATOR =========================
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        return f(*args, **kwargs)
    return wrapper

# ========================= FRONTEND ROUTES =========================
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/events")
def events_page():
    return render_template("events.html")

@app.route("/gallery")
def gallery_page():
    return render_template("gallery.html")

@app.route("/council")
def council():
    return render_template("council.html")

# ========================= ADMIN LOGIN ROUTES =========================

# 1. Admin Login Page (Shows the form)
@app.route("/admin-login-page")
def admin_login_page():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin-login.html")

# 2. Admin Login Processing (Only POST)
@app.route('/admin-login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        username = data.get('user')
        password = data.get('pass')

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_users WHERE username = %s", (username,))
        admin_user = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin_user and check_password_hash(admin_user['password'], password):
            session["admin_logged_in"] = True
            session["role"] = admin_user.get("role", "admin")
            return jsonify({
                "success": True,
                "redirect": "/admin/dashboard"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Invalid username or password"
            })

    except Exception as e:
        print("Login Error:", e)
        return jsonify({"success": False, "message": "Internal server error"}), 500

# Admin Dashboard (Protected)
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin-dashboard.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ========================= API ROUTES =========================

# Get Events (for side panel)
@app.route("/api/events", methods=["GET"])
def get_events():
    events = fetch_all("SELECT * FROM events ORDER BY date DESC")
    return jsonify(events)

# Add Event (Admin only)
@app.route('/api/events', methods=['POST'])
@admin_required
def add_event():
    try:
        data = request.get_json()

        event_name = data.get('event_name')
        description = data.get('description')
        date = data.get('date')
        time = data.get('time')
        venue = data.get('venue')
        team = data.get('team')
        status = data.get('status', 'upcoming')

        if not event_name or not date:
            return jsonify({"error": "Missing required fields"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO events (event_name, description, date, time, venue, team, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (event_name, description, date, time, venue, team, status))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Event added successfully"}), 201

    except Exception as e:
        print("ERROR:", str(e))  # 🔥 IMPORTANT
        return jsonify({"error": str(e)}), 500

@app.route("/api/events/<int:event_id>", methods=["DELETE"])
@admin_required
def delete_event(event_id):
    execute_query("DELETE FROM events WHERE id=%s", (event_id,))
    return jsonify({"message": "Deleted"})

@app.route("/api/events/<int:event_id>/complete", methods=["PUT"])
@admin_required
def mark_completed(event_id):
    execute_query(
        "UPDATE events SET status='past' WHERE id=%s",
        (event_id,)
    )
    return jsonify({"message": "Marked completed"})


# Gallery APIs
@app.route("/api/gallery", methods=["GET"])
def get_gallery():
    gallery = fetch_all("SELECT * FROM gallery ORDER BY id DESC")
    return jsonify(gallery)

@app.route("/api/gallery", methods=["POST"])
@admin_required
def add_gallery():
    try:
        title = request.form.get("title", "Untitled")
        file = request.files.get("image")

        if not file or not file.filename:
            return jsonify({"success": False, "message": "No image uploaded"}), 400

        filename = file.filename
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        execute_query(
            "INSERT INTO gallery (title, image) VALUES (%s, %s)",
            (title, filename)
        )
        return jsonify({"success": True, "message": "Image added to gallery"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route("/api/event-gallery/<int:event_id>", methods=["POST"])
@admin_required
def upload_event_gallery(event_id):
    files = request.files.getlist("gallery_images")

    for file in files:
     if file and file.filename:
              filename = secure_filename(file.filename)
              filename = f"{event_id}_{int(time.time())}_{filename}"
              file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

     execute_query(
            "INSERT INTO event_gallery (event_id, image) VALUES (%s, %s)",
            (event_id, filename)
        )

           

            

    return jsonify({"success": True})

@app.route("/api/event-gallery/<int:event_id>", methods=["GET"])
def get_event_gallery(event_id):
    images = fetch_all(
        "SELECT image FROM event_gallery WHERE event_id=%s",
        (event_id,)
    )
    return jsonify(images)



@app.route("/api/gallery/completed")
def completed_gallery():
    data = fetch_all("""
        SELECT e.id, e.event_name, e.date, g.image
        FROM events e
        JOIN event_gallery g ON e.id = g.event_id
        WHERE e.status = 'past'
        ORDER BY e.date DESC
    """)
    return jsonify(data)

@app.route("/api/completed-events", methods=["GET"])
def get_completed_events():
    events = fetch_all("""
        SELECT id, event_name 
        FROM events 
        WHERE status = 'past'
        ORDER BY date DESC
    """)
    return jsonify(events)

        

# ========================= RUN THE APP =========================
if __name__ == "__main__":
    app.run(debug=True, port=5000)