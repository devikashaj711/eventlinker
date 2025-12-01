
from flask import Blueprint, render_template, session
from database import get_db_connection, close_db_connection


from flask import g
from flask import request, redirect, url_for, flash
from datetime import datetime

# AI Similarity
import json
import numpy as np
from ai_utils import embed_text, json_to_embedding, cosine_sim

attendee_bp = Blueprint('attendee_bp', __name__)


@attendee_bp.route('/attendee/event/<int:event_id>')
def attendee_event_details(event_id):
    conn = get_db_connection()
    event = None
    user_id = session.get('user_id')  # Current logged-in attendee

    # If 'registered=1' is in URL, we came from Registered Events
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
                ORDER BY e.modified_date DESC;
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

@attendee_bp.route('/register_event/<int:event_id>')
def register_event(event_id):
    user_id = session.get("user_id")

    # If not logged in → redirect to login
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

            # Check if already registered
            cursor.execute("""
                SELECT registration_id 
                FROM event_registrations 
                WHERE user_id = %s AND event_id = %s
            """, (user_id, event_id))
            existing = cursor.fetchone()

            if existing:
                flash("You are already registered for this event!", "warning")
            else:
                # Register the attendee
                cursor.execute("""
                    INSERT INTO event_registrations (event_id, user_id, created_date)
                    VALUES (%s, %s, NOW())
                """, (event_id, user_id))
                conn.commit()
                flash("Successfully registered for the event!", "success")

        finally:
            close_db_connection(conn, cursor)

    # Redirect to that event’s details
    return redirect(
        url_for('attendee_bp.attendee_event_details', event_id=event_id, registered=1)
    )



@attendee_bp.route('/attendee_homepage')
def attendee_homepage():

    # Require login (both organizers and attendees are allowed)
    if "user_id" not in session:
        flash("Please log in", "danger")
        return redirect(url_for('user_bp.login_user'))
    
    conn = get_db_connection()
    events = []
    is_organizer = (session.get("user_role_id") == 1)

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM event_details ORDER BY event_date ASC")
            events = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    is_organizer = (session.get("user_role_id") == 1)
    active_role = session.get("active_role", "attendee")

    return render_template(
        'attendee_homepage.html',
        events=events,
        is_organizer=is_organizer,
        active_role=active_role
    )


# ------------------------------
# Member list page
# ------------------------------
# ------------------------------
# Member list page
# ------------------------------
@attendee_bp.route('/attendee/event/<int:event_id>/members')
def attendee_member_list(event_id):
    conn = get_db_connection()
    members = []
    user_id = session.get('user_id')  # current logged-in attendee

    # Default back URL: Event Details page
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
                       ON ( (ec.receiver_id = u.user_id AND ec.requester_id = %s)
                            OR
                            (ec.requester_id = u.user_id AND ec.receiver_id = %s) )
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


@attendee_bp.route('/about')
def about_page():
    user_role_id = session["user_role_id"]
    is_organizer = (user_role_id == 1)
    # Organizer (1) and pure attendee (2) can both act as attendee
    is_attendee = (user_role_id in (1, 2))

    # Which dashboard/view is currently active? (controlled by dropdown)
    active_role = session.get("active_role")

    # Decide where the main profile 'home/back' should go in the navbar
    profile_home = None
    if is_organizer and active_role == "attendee":
        profile_home = "attendee"
    elif is_organizer:
        profile_home = "organizer"
    elif is_attendee:
        profile_home = "attendee"
        
    return render_template('about_us.html', 
            is_attendee=is_attendee,
            is_organizer=is_organizer,
            profile_home=profile_home,
            active_role=active_role)

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
                SELECT event_id 
                FROM event_registrations
                WHERE user_id = %s
            """, (user_id,))
            rows = cursor.fetchall()

            if rows:
                event_id_list = [row['event_id'] for row in rows]
                placeholders = ','.join(['%s'] * len(event_id_list))
                query = f"""
                    SELECT e.*, c.category_name
                    FROM event_details e
                    LEFT JOIN event_category c ON e.category_id = c.category_id
                    WHERE e.event_id IN ({placeholders})
                    ORDER BY event_date ASC
                """
                cursor.execute(query, event_id_list)
                events = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template(
        "attendee_registered_events.html",
        events=events,
        from_registered=True
    )


@attendee_bp.route('/send_connection_request', methods=['POST'])
def send_connection_request():
    print("DEBUG: send_connection_request called")

    # Print the full session
    print("DEBUG: session contents =", dict(session))

    # Print the full form data
    print("DEBUG: form contents =", request.form)

    # Get requester and receiver
    requester_id = session.get('user_id')
    receiver_id = request.form.get('receiver_id')

    print("DEBUG: requester_id =", requester_id)
    print("DEBUG: receiver_id =", receiver_id)

    if not requester_id or not receiver_id:
        print("DEBUG: Invalid request, missing requester or receiver")
        flash("Invalid request, missing requester or receiver", "danger")
        return redirect(request.referrer)

    conn = get_db_connection()
    print("DEBUG: Database connection established:", conn)

    if conn:
        try:
            cursor = conn.cursor()
            print("DEBUG: Cursor created:", cursor)

            # Check if already exists
            cursor.execute("""
                SELECT * FROM event_connections 
                WHERE requester_id = %s AND receiver_id = %s
            """, (requester_id, receiver_id))

            existing = cursor.fetchone()
            print("DEBUG: Existing connection found:", existing)

            if existing:
                flash("Request already sent.", "warning")
                print("DEBUG: Flashing 'Request already sent'")
            else:
                cursor.execute("""
                    INSERT INTO event_connections
                    (requester_id, receiver_id, status_id, created_date, modified_date)
                    VALUES (%s, %s, %s, %s, %s)
                """, (requester_id, receiver_id, 2, datetime.now(), datetime.now()))

                conn.commit()
                flash("Connection request sent!", "success")
                print("DEBUG: Connection request inserted and committed")

        finally:
            close_db_connection(conn, cursor)
            print("DEBUG: Database connection closed")

    return redirect(request.referrer)


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
            # Get all requests where this user is the receiver and status is pending (1)
            cursor.execute("""
                SELECT ec.requester_id, ec.status_id, u.first_name, u.last_name
                FROM event_connections ec
                JOIN users u ON ec.requester_id = u.user_id
                WHERE ec.receiver_id = %s AND ec.status_id = 2
            """, (user_id,))
            requests = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template('connection_list.html', requests=requests)




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
                SET status_id = 1, modified_date = %s
                WHERE requester_id = %s AND receiver_id = %s
            """, (datetime.now(), requester_id, user_id))
            conn.commit()
            flash("Connection accepted!", "success")
        finally:
            close_db_connection(conn, cursor)

    return redirect(request.referrer)


@attendee_bp.before_app_request
def load_pending_requests_count():
    """Load pending connection request count for logged-in attendee."""
    user_id = session.get('user_id')
    g.pending_request_count = 0  # default: no requests

    if user_id:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT COUNT(*) AS pending_count
                    FROM event_connections
                    WHERE receiver_id = %s AND status_id = 2
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    g.pending_request_count = row['pending_count']
            finally:
                close_db_connection(conn, cursor)
                
                
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

            # Fetch all connected users (status = 2) where current user is either requester or receiver
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
                WHERE (ec.requester_id = %s OR ec.receiver_id = %s)
                  AND ec.status_id = 1
            """, (user_id, user_id, user_id, user_id))

            connections = cursor.fetchall()

        finally:
            close_db_connection(conn, cursor)

    return render_template("my_connection.html", connections=connections)
@attendee_bp.route('/user/<int:user_id>')
def view_user(user_id):
    conn = get_db_connection()
    user = None

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id, first_name, last_name, email, user_role_id,
                       insta_link, linkedin_link, interests
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            user = cursor.fetchone()
        finally:
            close_db_connection(conn, cursor)

    if not user:
        return "User not found", 404

    # Determine role name
    role_name = "Organizer" if user['user_role_id'] == 1 else "Attendee"

    return render_template("user_detail.html", user=user, role_name=role_name)


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
                SET status_id = 3, modified_date = %s
                WHERE requester_id = %s AND receiver_id = %s
            """, (datetime.now(), requester_id, user_id))
            conn.commit()
            # flash("Connection declined!", "success")
        finally:
            close_db_connection(conn, cursor)

    return ('', 204)  # Empty response for AJAX


@attendee_bp.route("/similarity")
def attendee_similarity():
    # 1) Auth + handle organizer-as-attendee
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("user_bp.login_user"))

    user_id = session["user_id"]
    user_role_id = session.get("user_role_id")
    active_role = session.get("active_role")

    # Organizer hitting this? Treat it as attendee view.
    if user_role_id == 1 and active_role != "attendee":
        session["active_role"] = "attendee"
        active_role = "attendee"

    if user_role_id not in (1, 2):
        flash("You are not allowed to access this page.", "danger")
        return redirect(url_for("user_bp.user_profile"))

    # 2) Pull user profile + registrations + upcoming events with embeddings
    conn = get_db_connection()
    user = None
    events = []
    registered_event_ids = set()

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)

            # User profile
            cursor.execute("""
                SELECT bio, interests
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            user = cursor.fetchone() or {}

            bio = user.get("bio") or ""
            interests = user.get("interests") or ""
            query_text = (bio + "\n" + interests).strip()
            if not query_text:
                query_text = "events I might like"

            # Already registered events
            cursor.execute("""
                SELECT event_id
                FROM event_registrations
                WHERE user_id = %s
            """, (user_id,))
            rows = cursor.fetchall()
            registered_event_ids = {r["event_id"] for r in rows}

            # Upcoming active events + embeddings
            cursor.execute("""
                SELECT event_id, event_title, description, event_date,
                       location, image_path, embedding
                FROM event_details
                WHERE is_active = 1
                  AND event_date >= NOW()
            """)
            events = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    if not events:
        return render_template("similarity.html",
                               recommended_events=[])

    # 3) Build QUERY embedding ONCE from profile text
    query_embedding = embed_text(query_text)

    # 4) Compute similarity using stored event embeddings
    scored_events = []
    for e in events:
        # Skip events user is already registered for
        if e["event_id"] in registered_event_ids:
            continue

        raw_emb = e.get("embedding")
        if not raw_emb:
            continue  # no embedding stored, skip

        try:
            event_emb = json_to_embedding(raw_emb)
        except Exception as ex:
            print(f"Error parsing embeddings for event {e['event_id']}: {ex}")
            continue

        score = cosine_sim(query_embedding, event_emb)
        e_with_score = dict(e)
        e_with_score["similarity_score"] = score
        scored_events.append(e_with_score)

    # 5) Sort & take top N
    scored_events.sort(key=lambda x: x["similarity_score"], reverse=True)
    top_events = scored_events[:10]

    return render_template(
        "similarity.html",
        recommended_events=top_events
    )
