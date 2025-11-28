from flask import Blueprint, render_template
from database import get_db_connection, close_db_connection

attendee_bp = Blueprint('attendee_bp', __name__)

@attendee_bp.route('/attendee/event/<int:event_id>')
def attendee_event_details(event_id):
    conn = get_db_connection()
    event = None

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT e.*, c.category_name 
                FROM event_details e
                LEFT JOIN event_category c ON e.category_id = c.category_id
                WHERE e.event_id = %s
            """, (event_id,))
            event = cursor.fetchone()
        finally:
            close_db_connection(conn, cursor)

    if not event:
        return "Event not found", 404

    return render_template("event_detail.html", event=event, is_attendee=True)


@attendee_bp.route('/attendee_homepage')
def attendee_homepage():
    conn = get_db_connection()
    events = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM event_details ORDER BY event_date ASC")
            events = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template('attendee_homepage.html', events=events)


# ------------------------------
# Member list page
# ------------------------------
@attendee_bp.route('/attendee/event/<int:event_id>/members')
def attendee_member_list(event_id):
    conn = get_db_connection()
    members = []

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.first_name, u.last_name, u.email
                FROM event_registrations er
                JOIN users u ON er.user_id = u.user_id
                WHERE er.event_id = %s
            """, (event_id,))
            members = cursor.fetchall()
        finally:
            close_db_connection(conn, cursor)

    return render_template("member_list.html", members=members, event_id=event_id)
