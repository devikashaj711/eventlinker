# -------------------------------------
# backend/organizer.py
# -------------------------------------

import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app
)
from werkzeug.utils import secure_filename
from database import get_db_connection, close_db_connection
import qrcode
from storage import upload_file_to_s3, upload_qr_to_s3, delete_from_s3

#AI Similarity
import json
from ai_utils import generate_embedding

# -------------------------------------
#  Blueprint Setup
# -------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_current_dir, "..")
_templates_folder = os.path.join(_project_root, "frontend", "templates")

organizer_bp = Blueprint(
    "organizer_bp",
    __name__,
    template_folder=_templates_folder,
)


# -------------------------------------
#  Helper: restrict organizer-only access
# -------------------------------------
def require_organizer():
    if "user_id" not in session or session.get("user_role_id") != 1:
        flash("Please login as organizer.", "danger")
        return False
    return True


# -------------------------------------
#  READ: Organizer Homepage → Event List
# -------------------------------------
@organizer_bp.route("/organizer_home")
def organizer_homepage():
    if not require_organizer():
        return redirect(url_for("login_user"))
    
    # 🔹 Mark that the user is currently viewing the organizer dashboard
    session["active_view"] = "organizer"

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = None
    events = []
    organizer_name = "Organizer"   # fallback

    try:
        cursor = conn.cursor(dictionary=True)

        # 🔹 Get organizer name (change table/columns to match your DB)
        cursor.execute("""
            SELECT first_name, last_name
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if user:
            # use full name or just first_name as you like
            organizer_name = f"{user['first_name']} {user['last_name']}".strip()

        # 🔹 Get events
        cursor.execute("""
            SELECT event_id, event_title, event_date, location
            FROM event_details
            WHERE created_by=%s AND is_active=1
            ORDER BY event_date DESC
        """, (user_id,))
        events = cursor.fetchall()
    finally:
        close_db_connection(conn, cursor)

    # Organizer is always true here
    is_organizer = True
    # If active_role isn't set yet (e.g., typed URL manually), default to organizer
    if session.get("active_role") not in ("organizer", "attendee"):
        session["active_role"] = "organizer"
    active_role = session.get("active_role", "organizer")

    return render_template(
        "organizer_homepage.html",
        events=events,
        organizer_name=organizer_name,
        success=request.args.get("success", ""),
        is_organizer=is_organizer,
        active_role=active_role,
    )



# -------------------------------------
#  CREATE (GET): Show Add Event form
# -------------------------------------
@organizer_bp.route("/add", methods=["GET"])
def add_event_page():
    """Show the Add Event page with category dropdown."""
    if not require_organizer():
        return redirect(url_for("login_user"))

    conn = get_db_connection()
    cursor = None
    categories = []

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT category_id, category_name "
            "FROM event_category ORDER BY category_name ASC"
        )
        categories = cursor.fetchall()
    finally:
        close_db_connection(conn, cursor)

    return render_template("add_event.html", categories=categories)



# -------------------------------------
#  CREATE: Save New Event
# -------------------------------------
@organizer_bp.route("/save_event", methods=["POST"])
def save_event():
    if not require_organizer():
        return redirect(url_for("login_user"))

    user_id = session["user_id"]

    title = request.form.get("title")
    description = request.form.get("description")
    category_id = request.form.get("category")
    location = request.form.get("location")
    date_str = request.form.get("date")

    # Convert date
    try:
        event_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
    except:
        flash("Invalid date format.", "danger")
        return redirect(url_for("organizer_bp.add_event_page"))


    # Validate future date
    if event_date < datetime.now():
        flash("Event date must be in the future.", "danger")
        return redirect(url_for("organizer_bp.add_event_page"))


    # Upload Event Image to S3
    image = request.files.get("image_file")
    # image_path = None

    # if image and image.filename.strip():
    #     try:
    #         image_path = upload_file_to_s3(image, "event_images")
    #     except Exception as e:
    #         print("Image upload error:", e)
    #         flash("Failed to upload event image.", "danger")
    #         return redirect(url_for("organizer_bp.add_event_page"))
        

    if image and hasattr(image, "filename") and image.filename:
        try:
            image_path = upload_file_to_s3(image, "event_images")
        except Exception as e:
            print("Image upload error:", e)
            flash("Failed to upload event image.", "danger")
            return redirect(url_for("organizer_bp.add_event_page"))
    else:
        image_path = None


    conn = get_db_connection()
    cursor = None

    try:
        cursor = conn.cursor()

        # ---------------------------------------------
        # 1️⃣ CREATE EVENT EMBEDDING
        # ---------------------------------------------
        embed_text = f"{title}. {description}. {location}"
        try:
            event_embedding = generate_embedding(embed_text)
        except Exception as e:
            print("Embedding generation error:", e)
            event_embedding = None

        # ---------------------------------------------
        # 2️⃣ INSERT EVENT WITH EMBEDDING COLUMN
        # ---------------------------------------------
        insert_sql = """
            INSERT INTO event_details 
            (category_id, event_title, description, event_date, location, 
             image_path, qr_code_path, created_by, is_active, created_date, embedding)
            VALUES (%s,%s,%s,%s,%s,%s,'qr_codes/sample.png',%s,1,NOW(),%s)
        """

        cursor.execute(insert_sql, (
            category_id, title, description, event_date,
            location, image_path, user_id,
            json.dumps(event_embedding)      # <–– NEW
        ))

        conn.commit()

        # Get event_id
        event_id = cursor.lastrowid


        # Generate QR code
        # qr_data = f"http://127.0.0.1:5000/organizer/event/{event_id}"
        qr_data = url_for('attendee_bp.register_event', event_id=event_id, _external=True)
        print('qr_data---', qr_data)
        qr_img = qrcode.make(qr_data)

        # Upload QR to S3
        try:
            qr_path = upload_qr_to_s3(qr_img, "qr_codes")
        except Exception as e:
            print("QR upload error:", e)
            flash("Failed to upload QR code.", "danger")
            return redirect(url_for("organizer_bp.add_event_page"))


        # Update event record with QR URL
        cursor.execute(
            "UPDATE event_details SET qr_code_path=%s, qr_link=%s WHERE event_id=%s",
            (qr_path, qr_data, event_id)
        )
        conn.commit()

        flash("Event created successfully!", "success")

    except Exception as e:
        print("ERROR saving event:", e)
        flash("Error saving event.", "danger")
        return redirect(url_for("organizer_bp.add_event_page"))

    finally:
        close_db_connection(conn, cursor)

    return redirect(url_for("organizer_bp.organizer_homepage", success="true"))




# -------------------------------------
#  READ: View Single Event
# -------------------------------------
@organizer_bp.route("/event/<int:event_id>")
def view_event(event_id):
    if not require_organizer():
        return redirect(url_for("login_user"))
    

    is_organizer = (session.get("user_role_id") == 1)
    print('organizer in view event organizer page--', is_organizer)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch event & category
    cursor.execute("""
        SELECT e.event_id, e.event_title, e.description, e.event_date, 
       e.location, e.image_path, e.qr_code_path,
       c.category_name
        FROM event_details e
        LEFT JOIN event_category c ON e.category_id = c.category_id
        WHERE e.event_id = %s AND e.created_by = %s
        ORDER BY e.modified_date DESC;
    """, (event_id, session["user_id"]))

    event = cursor.fetchone()

    close_db_connection(conn, cursor)

    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("organizer_bp.organizer_homepage"))

    return render_template("event_detail.html", event=event, is_organizer=is_organizer)



# -------------------------------------
#  UPDATE: Load Edit Page
# -------------------------------------
@organizer_bp.route("/event/<int:event_id>/edit")
def edit_event(event_id):
    if not require_organizer():
        return redirect(url_for("login_user"))

    conn = get_db_connection()
    cursor = None
    event = None
    categories = []

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM event_details WHERE event_id=%s AND created_by=%s",
            (event_id, session["user_id"])
        )
        event = cursor.fetchone()

        cursor.execute("SELECT * FROM event_category ORDER BY category_name ASC")
        categories = cursor.fetchall()
    finally:
        close_db_connection(conn, cursor)

    return render_template("edit_event.html", event=event, categories=categories)




# -------------------------------------
#  UPDATE: Save Edited Event
# -------------------------------------
@organizer_bp.route("/event/<int:event_id>/update", methods=["POST"])
def update_event(event_id):
    if not require_organizer():
        return redirect(url_for("login_user"))

    title = request.form.get("title")
    description = request.form.get("description")
    category_id = request.form.get("category")
    location = request.form.get("location")
    date_str = request.form.get("date")


    # Convert/update date
    try:
        new_event_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
    except:
        flash("Invalid date format.", "danger")
        return redirect(url_for("organizer_bp.edit_event", event_id=event_id))

    if new_event_date < datetime.now():
        flash("Event date must be in the future.", "danger")
        return redirect(url_for("organizer_bp.edit_event", event_id=event_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch existing event
    cursor.execute("""
        SELECT image_path, qr_code_path, qr_link, event_date
        FROM event_details
        WHERE event_id=%s AND created_by=%s
    """, (event_id, session["user_id"]))

    event = cursor.fetchone()

    if not event:
        flash("Event not found.", "danger")
        close_db_connection(conn, cursor)
        return redirect(url_for("organizer_bp.organizer_homepage"))

    old_image = event["image_path"]
    old_qr = event["qr_code_path"]
    old_qr_link = event["qr_link"]
    old_date = event["event_date"]


    # Image Upload Handling
    new_image = request.files.get("image_file")

    if new_image and new_image.filename.strip():
        # delete old image from S3
        if old_image:
            delete_from_s3(old_image)

        # upload new image
        new_image_path = upload_file_to_s3(new_image, "event_images")
    else:
        new_image_path = old_image


    # Regenerate QR Code if date changed
    regenerate_qr = False

    try:
        if new_event_date != old_date:
            regenerate_qr = True
    except:
        regenerate_qr = True

    if regenerate_qr:
        # delete old QR
        if old_qr:
            delete_from_s3(old_qr)

        # create new QR
        qr_data = url_for('attendee_bp.register_event', event_id=event_id, _external=True)
        qr_img = qrcode.make(qr_data)
        new_qr_path = upload_qr_to_s3(qr_img)
    else:
        new_qr_path = old_qr
        qr_data = old_qr_link



    # Update Event in DB
    cursor.execute("""
        UPDATE event_details
        SET category_id=%s,
            event_title=%s,
            description=%s,
            event_date=%s,
            location=%s,
            image_path=%s,
            qr_code_path=%s,
            qr_link=%s,
            modified_date=NOW()
        WHERE event_id=%s AND created_by=%s
    """, (
        category_id, title, description, new_event_date, location,
        new_image_path, new_qr_path, qr_data, event_id, session["user_id"]
    ))

    conn.commit()
    close_db_connection(conn, cursor)

    flash("Event updated successfully!", "success")
    return redirect(url_for("organizer_bp.organizer_homepage", success="true"))




# -------------------------------------
#  DELETE 
# -------------------------------------
@organizer_bp.route("/event/<int:event_id>/delete", methods=["POST"])
def delete_event(event_id):
    if not require_organizer():
        return redirect(url_for("login_user"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)


    # Step 1 — Fetch image + QR paths
    cursor.execute("""
        SELECT image_path, qr_code_path
        FROM event_details
        WHERE event_id=%s AND created_by=%s
    """, (event_id, session["user_id"]))

    event = cursor.fetchone()

    if not event:
        flash("Event not found.", "danger")
        close_db_connection(conn, cursor)
        return redirect(url_for("organizer_bp.organizer_homepage"))


    # Step 2 — Delete related registrations
    cursor.execute("""
        DELETE FROM event_registrations
        WHERE event_id=%s
    """, (event_id,))
    conn.commit()


    # Step 3 — Delete from S3
    if event["image_path"]:
        delete_from_s3(event["image_path"])

    if event["qr_code_path"]:
        delete_from_s3(event["qr_code_path"])


    # Step 4 — Delete event
    cursor.execute("""
        DELETE FROM event_details
        WHERE event_id=%s AND created_by=%s
    """, (event_id, session["user_id"]))
    conn.commit()

    close_db_connection(conn, cursor)

    flash("Event deleted successfully!", "success")
    return redirect(url_for("organizer_bp.organizer_homepage", success="true"))

