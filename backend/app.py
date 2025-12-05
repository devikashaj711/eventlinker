# -------------------------------------
# backend/app.py
# -------------------------------------

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from database import get_db_connection, close_db_connection
import os
import mysql.connector

# Import the blueprint
from organizer import organizer_bp
from attendee import attendee_bp
from user import user_bp


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



# --------------------------------------------------------------------
# Go to Organizer functionality
# Register the organizer blueprint at the root URL of the application.
# ---------------------------------------------------------------------
app.register_blueprint(organizer_bp, url_prefix='/organizer')


# --------------------------------------------------------------------
# Go to attendee functionality
# ---------------------------------------------------------------------
app.register_blueprint(attendee_bp, url_prefix='/attendee')


# --------------------------------------------------------------------
# Go to user functionality
# ---------------------------------------------------------------------
app.register_blueprint(user_bp)



# -------------------------------------
#  Landing Page Redirect
# -------------------------------------
@app.route('/')
def index():
    return redirect(url_for('user_bp.login_user'))



# ---------------------------------------------------------
#  8.4	main Execution Block – Start Development Server
# ---------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)

