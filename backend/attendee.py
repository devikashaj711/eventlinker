# -----------------------------------------------------
# backend/attendee.py
# -----------------------------------------------------

from flask import (
    Blueprint, render_template, session, request,
    redirect, url_for, flash, g
)

from database import get_db_connection, close_db_connection
from datetime import datetime
import json
import numpy as np
from ai_utils import generate_embedding

#Attendee blueprint
attendee_bp = Blueprint('attendee_bp', __name__)


# -----------------------------------------------------
# Display Attendee Homepage
# -----------------------------------------------------
@attendee_bp.route('/attendee_homepage')
def attendee_homepage():
    if "user_id" not in session:
        flash("Please log in", "danger")
        return redirect(url_for('user_bp.login_user'))

    conn = get_db_connection()
    events = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM event_details ORDER BY event_date ASC")
            events = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template(
        'attendee_homepage.html',
        events=events,
        is_organizer=(session.get("user_role_id") == 1),
        active_role=session.get("active_role", "attendee")
    )



# -----------------------------------------------------
# View Event Details based on event id
# -----------------------------------------------------
@attendee_bp.route('/attendee/event/<int:event_id>')
def attendee_event_details(event_id):
    conn = get_db_connection()
    event = None
    user_id = session.get('user_id')
    show_member_button = request.args.get("registered", "0") == "1"
    back_src = "registered" if show_member_button else "homepage"

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT e.*, c.category_name 
                FROM event_details e
                LEFT JOIN event_category c ON e.category_id = c.category_id
                WHERE e.event_id = %s
                ORDER BY e.modified_date DESC
            """, (event_id,))
            event = cursor.fetchone()
        finally:
            close_db_connection(conn, cursor)

    if not event:
        return "Event not found", 404

    return render_template(
        "event_detail.html",
        event=event,
        is_attendee=True,
        show_member_button=show_member_button,
        back_src=back_src
    )


# -----------------------------------------------------
# Register for Event
# -----------------------------------------------------
@attendee_bp.route('/register_event/<int:event_id>')
def register_event(event_id):
    user_id = session.get("user_id")

    if not user_id:
        session["redirect_after_login"] = url_for(
            'attendee_bp.register_event', event_id=event_id
        )
        flash("Please log in to register for the event", "info")
        return redirect(url_for('user_bp.login_user'))

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT registration_id 
                FROM event_registrations 
                WHERE user_id = %s AND event_id = %s
            """, (user_id, event_id))
            existing = cursor.fetchone()

            if existing:
                flash("You are already registered for this event!", "warning")
            else:
                cursor.execute("""
                    INSERT INTO event_registrations (event_id, user_id, created_date)
                    VALUES (%s, %s, NOW())
                """, (event_id, user_id))
                conn.commit()
                flash("Successfully registered!", "success")

        finally:
            close_db_connection(conn, cursor)

    return redirect(
        url_for('attendee_bp.attendee_event_details', event_id=event_id, registered=1)
    )


# -----------------------------------------------------
# View Event Attendee List
# -----------------------------------------------------
@attendee_bp.route('/attendee/event/<int:event_id>/members')
def attendee_member_list(event_id):
    conn = get_db_connection()
    members = []
    user_id = session.get('user_id')

    back_url = request.args.get(
        "back",
        url_for('attendee_bp.attendee_event_details', event_id=event_id)
    )

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.user_id, u.first_name, u.last_name, u.email,
                       ec.status_id,
                       CASE
                           WHEN ec.requester_id = %s THEN 'sent'
                           WHEN ec.receiver_id = %s THEN 'received'
                           ELSE NULL
                       END AS connection_direction
                FROM event_registrations er
                JOIN users u ON er.user_id = u.user_id
                LEFT JOIN event_connections ec
                       ON ((ec.receiver_id = u.user_id AND ec.requester_id = %s)
                           OR (ec.requester_id = u.user_id AND ec.receiver_id = %s))
                WHERE er.event_id = %s 
                  AND u.user_role_id = 2
            """, (user_id, user_id, user_id, user_id, event_id))
            members = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template(
        "member_list.html",
        members=members,
        event_id=event_id,
        back_url=back_url
    )


# -----------------------------------------------------
# View Registered Events
# -----------------------------------------------------
@attendee_bp.route('/registered')
def attendee_registered_events():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in", "danger")
        return redirect(url_for('user_bp.login_user'))

    conn = get_db_connection()
    events = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT event_id FROM event_registrations WHERE user_id = %s
            """, (user_id,))
            rows = cursor.fetchall()

            if rows:
                event_ids = [r['event_id'] for r in rows]
                placeholders = ','.join(['%s'] * len(event_ids))

                cursor.execute(f"""
                    SELECT e.*, c.category_name
                    FROM event_details e
                    LEFT JOIN event_category c ON e.category_id = c.category_id
                    WHERE e.event_id IN ({placeholders})
                    ORDER BY event_date ASC
                """, event_ids)

                events = cursor.fetchall()

        finally:
            close_db_connection(conn, cursor)

    return render_template(
        "attendee_registered_events.html",
        events=events,
        from_registered=True
    )


# -----------------------------------------------------
# Send Connection Request
# -----------------------------------------------------
@attendee_bp.route('/send_connection_request', methods=['POST'])
def send_connection_request():
    requester_id = session.get('user_id')
    receiver_id = request.form.get('receiver_id')

    if not requester_id or not receiver_id:
        flash("Invalid request", "danger")
        return redirect(request.referrer)

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM event_connections
                WHERE requester_id=%s AND receiver_id=%s
            """, (requester_id, receiver_id))
            already = cursor.fetchone()

            if already:
                flash("Request already sent.", "warning")
            else:
                cursor.execute("""
                    INSERT INTO event_connections
                    (requester_id, receiver_id, status_id, created_date, modified_date)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """, (requester_id, receiver_id, 2))
                conn.commit()
                flash("Connection request sent!", "success")

        finally:
            close_db_connection(conn, cursor)

    return redirect(request.referrer)


# -----------------------------------------------------
# View Incoming Connection Requests
# -----------------------------------------------------
@attendee_bp.route('/connections')
def attendee_connections():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in", "danger")
        return redirect(url_for('attendee_bp.attendee_homepage'))

    conn = get_db_connection()
    requests = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ec.requester_id, ec.status_id, u.first_name, u.last_name
                FROM event_connections ec
                JOIN users u ON ec.requester_id = u.user_id
                WHERE ec.receiver_id = %s AND ec.status_id = 2
            """, (user_id,))
            requests = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template("connection_list.html", requests=requests)


# -----------------------------------------------------
# Accept Connection Request
# -----------------------------------------------------
@attendee_bp.route('/accept_connection', methods=['POST'])
def accept_connection():
    user_id = session.get('user_id')
    requester_id = request.form.get('requester_id')

    if not user_id or not requester_id:
        flash("Invalid request", "danger")
        return redirect(request.referrer)

    conn = get_db_connection()

    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE event_connections
                SET status_id=1, modified_date=NOW()
                WHERE requester_id=%s AND receiver_id=%s
            """, (requester_id, user_id))
            conn.commit()
        finally:
            close_db_connection(conn, cursor)

    return redirect(request.referrer)


# -----------------------------------------------------
# Decline a Connection Request
# -----------------------------------------------------
@attendee_bp.route('/decline_connection', methods=['POST'])
def decline_connection():
    user_id = session.get('user_id')
    requester_id = request.form.get('requester_id')

    if not user_id or not requester_id:
        flash("Invalid request", "danger")
        return redirect(request.referrer)

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE event_connections
                SET status_id=3, modified_date=NOW()
                WHERE requester_id=%s AND receiver_id=%s
            """, (requester_id, user_id))
            conn.commit()
        finally:
            close_db_connection(conn, cursor)

    return ('', 204)


# -----------------------------------------------------
# Load Notification Count
# -----------------------------------------------------
@attendee_bp.before_app_request
def load_pending_requests_count():
    user_id = session.get('user_id')
    g.pending_request_count = 0

    if user_id:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT COUNT(*) AS pending_count
                    FROM event_connections
                    WHERE receiver_id=%s AND status_id=2
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    g.pending_request_count = row['pending_count']
            finally:
                close_db_connection(conn, cursor)



# -----------------------------------------------------
# View My Connections
# -----------------------------------------------------
@attendee_bp.route('/my-connections')
def attendee_my_connections():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_bp.login_user'))

    conn = get_db_connection()
    connections = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN ec.requester_id = %s THEN ec.receiver_id
                        ELSE ec.requester_id
                    END AS connected_user_id,
                    u.first_name,
                    u.last_name
                FROM event_connections ec
                JOIN users u 
                    ON u.user_id = CASE
                        WHEN ec.requester_id = %s THEN ec.receiver_id
                        ELSE ec.requester_id
                    END
                WHERE (ec.requester_id=%s OR ec.receiver_id=%s)
                  AND ec.status_id=1
            """, (user_id, user_id, user_id, user_id))
            connections = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template("my_connection.html", connections=connections)


# -----------------------------------------------------
# View Another User’s Profile
# -----------------------------------------------------
@attendee_bp.route('/user/<int:user_id>')
def view_user(user_id):
    conn = get_db_connection()
    user = None

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id, first_name, last_name, email, user_role_id,
                       bio, insta_link, linkedin_link, interests
                FROM users
                WHERE user_id=%s
            """, (user_id,))
            user = cursor.fetchone()
        finally:
            close_db_connection(conn, cursor)

    if not user:
        return "User not found", 404

    return render_template(
        "user_detail.html",
        user=user,
        role_name=("Organizer" if user["user_role_id"] == 1 else "Attendee")
    )


# -----------------------------------------------------
# Unregister from Event
# -----------------------------------------------------
@attendee_bp.route('/attendee/unregister_event', methods=['POST'])
def unregister_event():
    user_id = session.get('user_id')
    event_id = request.form.get('event_id')

    if not user_id or not event_id:
        flash("Invalid request.", "error")
        return redirect(url_for('attendee_bp.attendee_registered_events'))

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM event_registrations
            WHERE user_id=%s AND event_id=%s
        """, (user_id, event_id))
        conn.commit()

        flash("Unregistered successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash("Failed to unregister", "error")
    finally:
        close_db_connection(conn, cursor)

    return redirect(url_for('attendee_bp.attendee_registered_events', from_registered=1))


# -----------------------------------------------------
# Display About Us Page
# -----------------------------------------------------
@attendee_bp.route('/about')
def about_page():
    user_role_id = session["user_role_id"]
    is_organizer = (user_role_id == 1)
    active_role = session.get("active_role")

    if is_organizer and active_role == "attendee":
        profile_home = "attendee"
    elif is_organizer:
        profile_home = "organizer"
    else:
        profile_home = "attendee"

    return render_template(
        'about_us.html',
        is_attendee=True,
        is_organizer=is_organizer,
        profile_home=profile_home,
        active_role=active_role
    )

# =====================================================================
#                     AI-POWERED SIMILARITY ENGINE
# =====================================================================

# -----------------------------------------------------
# Cosine Similarity Helper
# -----------------------------------------------------
def cosine_sim(a, b):
    a = np.array(a)
    b = np.array(b)

    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return None

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ---------------------------------------------------------
# Generate Personalized Event Recommendations
# ---------------------------------------------------------
@attendee_bp.route("/similarity")
def attendee_similarity():

    # LOGIN CHECK
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("user_bp.login_user"))

    user_id = session["user_id"]

    # FETCH USER
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT bio, interests, embedding
        FROM users
        WHERE user_id=%s
    """, (user_id,))
    user_row = cursor.fetchone()

    if not user_row or not user_row["embedding"]:
        flash("Please update your Bio & Interests first.", "warning")
        return redirect(url_for("attendee_bp.attendee_homepage"))

    user_embedding = json.loads(user_row["embedding"])

    # Extract interest keywords
    interests = user_row["interests"] or ""
    interest_keywords = [
        w.strip().lower()
        for w in interests.replace(",", " ").split()
        if w.strip()
    ]

    # FETCH ALL ACTIVE UPCOMING EVENTS
    cursor.execute("""
        SELECT e.event_id, e.event_title, e.description, e.event_date,
               e.location, e.image_path, e.embedding, c.category_name
        FROM event_details e
        LEFT JOIN event_category c ON e.category_id = c.category_id
        WHERE e.event_date >= NOW()
          AND e.is_active = 1
    """)
    events = cursor.fetchall()
    conn.close()

    # CATEGORY MATCH COLLECTION
    category_matched = set()

    for e in events:
        category = (e.get("category_name") or "").lower()
        category_words = category.replace("&", " ").replace("-", " ").split()

        if any(k == cw for k in interest_keywords for cw in category_words):
            category_matched.add(e["event_id"])


    # SCORE CALCULATION
    scored = []
    CATEGORY_BOOST = 0.20
    SIMILARITY_THRESHOLD = 0.20

    for e in events:
        raw_emb = e["embedding"]
        if not raw_emb:
            continue

        try:
            event_vec = json.loads(raw_emb)
        except:
            continue

        score = cosine_sim(user_embedding, event_vec)
        if score is None or score != score:
            score = 0

        # BOOST category match
        if e["event_id"] in category_matched:
            score += CATEGORY_BOOST

        # Keep category matches even with low similarity
        if e["event_id"] in category_matched:
            keep = True
        else:
            keep = score >= SIMILARITY_THRESHOLD

        if keep:
            e["similarity_score"] = score
            scored.append(e)

    # SORT by final score
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)

    return render_template("similarity.html", recommended_events=scored[:20])
