# -------------------------------------
#  backend/user.py 
# -------------------------------------

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection, close_db_connection
import random, os
import smtplib
from email.mime.text import MIMEText
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException



user_bp = Blueprint('user_bp', __name__, template_folder='../frontend/templates')


# ------------------------------
#  LOGIN PAGE & FUNCTIONALITY
# ------------------------------
@user_bp.route('/login', methods=['GET', 'POST'])
def login_user():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Save email for reset password popup
        session["last_login_email"] = email

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

@user_bp.route('/send-reset-otp', methods=['POST'])
def send_reset_otp():
    email = request.form.get("email")

    # Check if email exists in DB
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        flash("Email not found.", "danger")
        return redirect(url_for('user_bp.login_user'))

    # Generate OTP
    otp = str(random.randint(100000, 999999))

    # Store OTP & email in session
    session["reset_email"] = email
    session["reset_otp"] = otp

    subject = "Your EventLinker Password Reset OTP"

    # SEND EMAIL THROUGH BREV0
    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        html_content = f"""
        <h2>Your OTP Code</h2>
        <p>Your password reset OTP is:</p>
        <h1 style="font-size:32px; letter-spacing:4px;">{otp}</h1>
        <p>Do not share this code with anyone.</p>
        """

        email_data = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": email}],
            sender={"email": "devikashaj711@gmail.com", "name": "EventLinker"},
            subject=subject,
            html_content=html_content
        )

        api_instance.send_transac_email(email_data)

        flash("OTP sent to your email!", "success")
        session["open_otp_modal"] = True

    except Exception as e:
        print("Brevo Email Error:", e)
        flash("Failed to send OTP. Try again later.", "danger")

    return redirect(url_for("user_bp.login_user"))


@user_bp.route('/verify-reset-otp', methods=['POST'])
def verify_reset_otp():
    typed_otp = request.form.get("otp")

    if typed_otp == session.get("reset_otp"):
        session["otp_verified"] = True
        session["open_password_modal"] = True
        flash("OTP verified successfully!", "success")
    else:
        flash("Incorrect OTP. Try again.", "danger")
        session["open_otp_modal"] = True

    return redirect(url_for('user_bp.login_user'))

@user_bp.route('/direct-reset-password', methods=['POST'])
def direct_reset_password():
    if not session.get("otp_verified"):
        flash("OTP verification required.", "danger")
        return redirect(url_for('user_bp.login_user'))

    new_password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        session["open_password_modal"] = True
        return redirect(url_for('user_bp.login_user'))

    email = session.get("reset_email")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET password=%s WHERE email=%s",
                   (new_password, email))
    conn.commit()
    close_db_connection(conn, cursor)

    # Clean up session
    session.pop("reset_email", None)
    session.pop("reset_otp", None)
    session.pop("otp_verified", None)

    flash("Password updated successfully!", "success")

    return redirect(url_for('user_bp.login_user'))


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

    # is_attendee = false
    # if "user_role_id" is 2:
    #     is_attendee=True
    # else:
    #     is_attendee=false

    is_attendee = (user_role_id == 2)

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

    return render_template("profile.html", user=user, is_attendee=is_attendee)


# ------------------------
#  LOGOUT FUNCTIONALITY
# ------------------------
@user_bp.route('/logout')
def logout_user():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('user_bp.login_user'))

