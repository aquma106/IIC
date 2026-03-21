# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------
# App Setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "supersecretkey123"

# Upload folder
UPLOAD_FOLDER = 'static/images'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# -------------------------
# Database
# -------------------------
def get_connection():
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='Kaularu@1234',  # Replace
            database='iic_website'
        )
        return conn
    except Error as e:
        print("DB Connection Error:", e)
        return None

# -------------------------
# Tables creation
# -------------------------
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    # Admin
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE,
        password VARCHAR(100)
    )
    """)
    # Faculty
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faculty_coordinators (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(100),
        branch VARCHAR(50),
        email VARCHAR(100),
        password VARCHAR(100),
        photo VARCHAR(255)
    )
    """)
    # Student
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_coordinators (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(100),
        branch VARCHAR(50),
        year INT,
        email VARCHAR(100),
        password VARCHAR(100),
        photo VARCHAR(255)
    )
    """)
    # Teams
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INT AUTO_INCREMENT PRIMARY KEY,
        team_name VARCHAR(100),
        description VARCHAR(255)
    )
    """)
    # Members
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(100),
        branch VARCHAR(50),
        year INT,
        role VARCHAR(50),
        email VARCHAR(100),
        photo VARCHAR(255),
        team_id INT,
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
    )
    """)
    # Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_name VARCHAR(100),
        description TEXT,
        date DATE
    )
    """)
    # Registrations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_registrations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_id INT,
        student_id INT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES events(id),
        FOREIGN KEY (student_id) REFERENCES student_coordinators(id)
    )
    """)
    # Default Admin
    cursor.execute("""
    INSERT IGNORE INTO admin_users (username, password) VALUES ('admin','admin123')
    """)
    conn.commit()
    cursor.close()
    conn.close()

create_tables()

# -------------------------
# Helpers
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filepath
    return ""

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

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'admin_logged_in' in session:
            return f(*args, **kwargs)
        flash("Admin login required!", "danger")
        return redirect(url_for('admin_login'))
    return wrap

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'faculty_logged_in' in session:
            return f(*args, **kwargs)
        flash("Faculty login required!", "danger")
        return redirect(url_for('faculty_login'))
    return wrap

def student_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'student_logged_in' in session:
            return f(*args, **kwargs)
        flash("Student login required!", "danger")
        return redirect(url_for('student_login'))
    return wrap

# -------------------------
# HTML Routes
# -------------------------
@app.route("/")
def splash():
    return render_template("splash.html")

# HOME PAGE
@app.route("/home")
def home():
    return render_template("home.html")

# Admin
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        user = request.form['username']
        pwd = request.form['password']
        res = fetch_all("SELECT * FROM admin_users WHERE username=%s AND password=%s",(user,pwd))
        if res:
            session['admin_logged_in']=True
            session['admin_user']=user
            return redirect(url_for('admin_dashboard'))
        else: flash("Invalid credentials","danger")
    return render_template('admin-login.html')

@app.route('/admin/logout')
def admin_logout(): session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard(): return render_template('admin-dashboard.html')

@app.route('/faculty-login')
def faculty_login(): return render_template('faculty-login.html')
@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard(): return render_template('faculty-dashboard.html')

@app.route('/student-coordinator/login')
def student_login(): return render_template('student-coordinator-login.html')
@app.route('/student-coordinator/dashboard')
@student_required
def student_dashboard(): return render_template('student-coordinator-dashboard.html')

@app.route('/events')
def events_page(): return render_template('events.html')

# -------------------------
# Password Reset Routes
# -------------------------
@app.route('/reset-password', methods=['GET','POST'])
def reset_password():
    if request.method=='POST':
        email = request.form['email']
        new_pwd = request.form['new_password']
        # Check Admin
        res = fetch_all("SELECT * FROM admin_users WHERE username=%s",(email,))
        if res: execute_query("UPDATE admin_users SET password=%s WHERE username=%s",(new_pwd,email))
        # Check Faculty
        elif fetch_all("SELECT * FROM faculty_coordinators WHERE email=%s",(email,)):
            execute_query("UPDATE faculty_coordinators SET password=%s WHERE email=%s",(new_pwd,email))
        # Check Student
        elif fetch_all("SELECT * FROM student_coordinators WHERE email=%s",(email,)):
            execute_query("UPDATE student_coordinators SET password=%s WHERE email=%s",(new_pwd,email))
        else: flash("Email not found!","danger"); return redirect(url_for('reset_password'))
        flash("Password updated successfully!","success")
        return redirect(url_for('home'))
    return render_template('reset-password.html')

# -------------------------
# API Routes with File Upload & CRUD
# -------------------------
# Example: Add Faculty
@app.route('/api/faculty', methods=['POST'])
@admin_required
def api_add_faculty():
    data = request.form
    file = request.files.get('photo')
    path = save_file(file)
    execute_query(
        "INSERT INTO faculty_coordinators (full_name, branch, email, password, photo) VALUES (%s,%s,%s,%s,%s)",
        (data['full_name'], data['branch'], data['email'], data['password'], path)
    )
    return jsonify({"message":"Faculty added successfully","photo":path})

# Similarly, you can replicate API routes for:
# Teams, Students, Members, Events, Registrations
# With GET/POST/PUT/DELETE and admin/faculty/student permissions

# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)