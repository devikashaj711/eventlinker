# -------------------------------------
# backend/app.py
# -------------------------------------

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from database import get_db_connection, close_db_connection
import os
import mysql.connector

# Import the organizer blueprint from backend/organizer_homepage.py
from organizer import organizer_bp
from attendee import attendee_bp


from dotenv import load_dotenv
load_dotenv()


# Set paths for static files and templates located in the frontend folder.
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_current_dir, '..') # Go up one level to EVENT-LINKER/

_static_folder = os.path.join(_project_root, 'frontend') # Flask serves static files from here
_main_templates_folder = os.path.join(_project_root, 'frontend', 'templates') # Default templates for app.py's own routes

app = Flask(
    __name__,
    static_folder=_static_folder,
    template_folder=_main_templates_folder
)
app.secret_key = "eventlinker_secret_key"


# --------------------------------------------
#  Save files in backend folder functionality
# ---------------------------------------------

# Commented this file code and added aws s3 bucket code -- madhuri
# # Path: backend/files
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_FOLDER = os.path.join(BASE_DIR, 'files')
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # Make sure folder exists
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # Serve event images
# @app.route('/files/images/<path:filename>')
# def serve_event_images(filename):
#     return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), filename)

# # Serve QR Code images
# @app.route('/files/qr_codes/<path:filename>')
# def serve_qr_codes(filename):
#     return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'qr_codes'), filename)



# --------------------------------------------------------------------
# Go to Organizer functionality
# Register the organizer blueprint at the root URL of the application.
# ---------------------------------------------------------------------
app.register_blueprint(organizer_bp, url_prefix='/organizer')
app.register_blueprint(attendee_bp)




# -------------------------------------
#  Login Functionality
# -------------------------------------

# Commented this login render code as we have already login user method below -- madhuri
# This route would look for 'login.html' in the _main_templates_folder.
# @app.route('/login')
# def login_page():
#     return render_template('login.html')

# Our first landing page is login page hence redirected to login method -- madhuri
@app.route('/')
def index():
    return redirect(url_for('login_user'))


@app.route('/login', methods=['GET', 'POST'])
def login_user():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM users WHERE email = %s AND password = %s"
                cursor.execute(query, (email, password))
                user = cursor.fetchone()

                if user:
                    flash("Login successful! Welcome back.", "success")

                    # SAVE USER IN SESSION
                    session["user_id"] = user["user_id"]
                    session["user_role_id"] = user["user_role_id"]

                    # Redirect based on user role
                    print(user['user_role_id'])
                    if user['user_role_id'] == 1:
                        return redirect(url_for('organizer_bp.organizer_homepage'))
                    elif user['user_role_id'] == 2:
                        return redirect(url_for('attendee_bp.attendee_homepage'))
                    else:
                        flash("Unknown user role. Contact support.", "danger")
                        return redirect(url_for('login_user'))
                else:
                    flash("Invalid email or password. Please try again.", "danger")

            except Exception as e:
                print(f"Error during login: {e}")
                flash("Something went wrong. Please try again.", "danger")
            finally:
                close_db_connection(conn, cursor)
    
    return render_template('login.html')




# -------------------------------------
#  New user registration Functionality
# -------------------------------------

@app.route('/register')
def register_page():
    return render_template('user_registration.html')

#Commented this method as first landing page is login page -- madhuri
# @app.route('/')
# def index():
#     return redirect(url_for('register_page'))


@app.route('/register_user', methods=['POST'])
def register_user():
    role = request.form.get('role')
    first_name = request.form.get('first-name')
    last_name = request.form.get('last-name')
    email = request.form.get('email')
    password = request.form.get('password')
    bio = request.form.get('bio')
    interests = request.form.get('interest')
    insta_link = request.form.get('instalink')
    linkedin_link = request.form.get('linkedinlink')

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            user_role_id = 1 if role == 'organizer' else 2

            query = """
                INSERT INTO users 
                (user_role_id, email, password, first_name, last_name, bio, interests, insta_link, linkedin_link, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            values = (user_role_id, email, password, first_name, last_name, bio, interests, insta_link, linkedin_link)
            cursor.execute(query, values)
            conn.commit()
            flash("✅ Account created successfully! Please log in.", "success")
        except Exception as e:
            print(f"❌ Error inserting user: {e}")
            flash("Error creating account. Please try again.", "danger")
        finally:
            close_db_connection(conn, cursor)

    return redirect(url_for('login_user'))


# @app.route('/attendee_homepage')
# def attendee_homepage():
#     conn = get_db_connection()
#     events = []

#     if conn:
#         try:
#             cursor = conn.cursor(dictionary=True)
#             query = "SELECT * FROM event_details ORDER BY event_date ASC"
#             cursor.execute(query)
#             events = cursor.fetchall()
#         except Exception as e:
#             print("Error fetching events:", e)
#         finally:
#             close_db_connection(conn, cursor)

#     return render_template('attendee_homepage.html', events=events)



# -------------------------------------
#  Main Method
# -------------------------------------
if __name__ == '__main__':
    app.run(debug=True)

