# -------------------------------------
#  backend/user.py 
# -------------------------------------

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection, close_db_connection

user_bp = Blueprint('user_bp', __name__, template_folder='../frontend/templates')


# ------------------------------
#  LOGIN PAGE & FUNCTIONALITY
# ------------------------------
@user_bp.route('/login', methods=['GET', 'POST'])
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

                    # Save session
                    session["user_id"] = user["user_id"]
                    session["user_role_id"] = user["user_role_id"]

                    # Redirect by user role
                    if user["user_role_id"] == 1:
                        return redirect(url_for('organizer_bp.organizer_homepage'))
                    elif user["user_role_id"] == 2:
                        return redirect(url_for('attendee_bp.attendee_homepage'))
                    else:
                        flash("Unknown user role. Contact admin.", "danger")
                        return redirect(url_for('user_bp.login_user'))
                else:
                    flash("Invalid email or password.", "danger")

            except Exception as e:
                print(f"Login error: {e}")
                flash("Something went wrong. Try again.", "danger")

            finally:
                close_db_connection(conn, cursor)

    return render_template('login.html')



# ------------------------------
#  REGISTRATION PAGE
# ------------------------------
@user_bp.route('/register')
def register_page():
    return render_template('user_registration.html')



# ------------------------------
#  REGISTER NEW USER
# ------------------------------
@user_bp.route('/register_user', methods=['POST'])
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
            values = (
                user_role_id, email, password, first_name,
                last_name, bio, interests, insta_link, linkedin_link
            )

            cursor.execute(query, values)
            conn.commit()

            flash("Account created successfully! Please log in.", "success")

        except Exception as e:
            print("Error registering user:", e)
            flash("Error creating account. Try again.", "danger")

        finally:
            close_db_connection(conn, cursor)

    return redirect(url_for('user_bp.login_user'))


@user_bp.route('/profile')
def user_profile():
    # user must be logged in
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('user_bp.login_user'))

    user_id = session["user_id"]
    print('user_id----', user_id)

    user_role_id = session["user_role_id"]
    print('user_role_id----', user_role_id)

    conn = get_db_connection()
    user = None

    if conn:
        try:
            # cursor = conn.cursor(dictionary=True)
            # cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            # user = cursor.fetchone()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM users WHERE user_id = %s AND user_role_id = %s"
            cursor.execute(query, (session["user_id"], session["user_role_id"]))
            user = cursor.fetchone()

        except Exception as e:
            print("Profile fetch error:", e)
        finally:
            close_db_connection(conn, cursor)

    return render_template("profile.html", user=user)


# ------------------------
#  LOGOUT FUNCTIONALITY
# ------------------------
@user_bp.route('/logout')
def logout_user():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('user_bp.login_user'))

