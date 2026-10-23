import csv
import io
import os
import uuid
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "college_events"),
    )


def save_event_image(upload):
    if not upload or not upload.filename:
        return None

    safe_name = secure_filename(upload.filename)

    if "." not in safe_name:
        raise ValueError("Choose a JPG, JPEG, PNG, or WEBP image.")

    extension = safe_name.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Image must be JPG, JPEG, PNG, or WEBP.")

    filename = f"{uuid.uuid4().hex}.{extension}"
    upload.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    sql = """
        SELECT e.*,
               (SELECT COUNT(*) FROM registrations r
                WHERE r.event_id = e.id) AS registration_count
        FROM events e
        WHERE e.status = 'Published'
    """
    values = []

    if search:
        sql += """
            AND (e.title LIKE %s OR e.category LIKE %s OR e.venue LIKE %s)
        """
        term = f"%{search}%"
        values = [term, term, term]

    sql += " ORDER BY e.event_date"
    cursor.execute(sql, values)
    events = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("index.html", events=events, search=search)


@app.route("/register/<int:event_id>", methods=["GET", "POST"])
def register(event_id):
    connection = get_db()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM events WHERE id=%s AND status='Published'",
        (event_id,),
    )
    event = cursor.fetchone()
    cursor.close()
    connection.close()

    if not event:
        flash("This event is not open for registration.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        student_no = request.form.get("student_no", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()

        if not all([student_no, name, email, department]):
            flash("Please fill in every field.", "danger")
            return render_template("register.html", event=event)

        connection = get_db()
        cursor = connection.cursor()

        try:
            connection.start_transaction()

            cursor.execute(
                "SELECT capacity FROM events WHERE id=%s FOR UPDATE",
                (event_id,),
            )
            row = cursor.fetchone()

            if row is None:
                raise ValueError("Event no longer exists.")

            capacity = row[0]

            cursor.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id=%s",
                (event_id,),
            )
            current_count = cursor.fetchone()[0]

            if capacity is not None and current_count >= capacity:
                connection.rollback()
                flash("Sorry, this event is full.", "warning")
                return render_template("register.html", event=event)

            cursor.execute(
                """
                INSERT INTO students (student_no, full_name, email, department)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    full_name=VALUES(full_name),
                    email=VALUES(email),
                    department=VALUES(department)
                """,
                (student_no, name, email, department),
            )

            cursor.execute(
                "SELECT id FROM students WHERE student_no=%s",
                (student_no,),
            )
            student_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO registrations (student_id, event_id)
                VALUES (%s, %s)
                """,
                (student_id, event_id),
            )

            connection.commit()
            flash("Registration successful!", "success")
            return redirect(url_for("index"))

        except mysql.connector.IntegrityError:
            connection.rollback()
            flash(
                "This student is already registered for this event.",
                "warning",
            )
        except (mysql.connector.Error, ValueError) as error:
            connection.rollback()
            flash(f"Could not complete registration: {error}", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template("register.html", event=event)


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND role='admin'",
            (username,),
        )
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session["admin_id"] = user["id"]
            session["admin_name"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Incorrect username or password.", "danger")

    return render_template("login.html")


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin/users/new", methods=["GET", "POST"])
@admin_required
def create_admin_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(username) < 3:
            flash("Username must have at least 3 characters.", "danger")
        elif len(password) < 10:
            flash("Password must have at least 10 characters.", "danger")
        elif password != confirm_password:
            flash("The passwords do not match.", "danger")
        else:
            connection = get_db()
            cursor = connection.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, 'admin')
                    """,
                    (username, generate_password_hash(password)),
                )
                connection.commit()
                flash("New admin account created.", "success")
                return redirect(url_for("dashboard"))

            except mysql.connector.IntegrityError:
                connection.rollback()
                flash("That username is already in use.", "danger")

            finally:
                cursor.close()
                connection.close()

    return render_template("admin_create.html")


@app.route("/admin")
@admin_required
def dashboard():
    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.*,
               (SELECT COUNT(*) FROM registrations r
                WHERE r.event_id = e.id) AS registration_count
        FROM events e
        ORDER BY e.event_date DESC
    """)
    events = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM students")
    student_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM registrations")
    registration_count = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        events=events,
        student_count=student_count,
        registration_count=registration_count,
    )


@app.route("/admin/events/new", methods=["GET", "POST"])
@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@admin_required
def event_form(event_id=None):
    connection = get_db()
    cursor = connection.cursor(dictionary=True)
    event = None

    if event_id:
        cursor.execute("SELECT * FROM events WHERE id=%s", (event_id,))
        event = cursor.fetchone()

        if not event:
            cursor.close()
            connection.close()
            return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        venue = request.form.get("venue", "").strip()
        event_date = request.form.get("event_date")
        capacity = request.form.get("capacity") or None
        status = request.form.get("status", "Draft")

        image_filename = event["image_filename"] if event else None
        upload = request.files.get("image")

        try:
            if upload and upload.filename:
                image_filename = save_event_image(upload)
        except ValueError as error:
            flash(str(error), "danger")
            cursor.close()
            connection.close()
            return render_template("event_form.html", event=event)

        if not title or not event_date:
            flash("Event title and date are required.", "danger")
        else:
            values = (
                title,
                description,
                category,
                venue,
                event_date,
                capacity,
                status,
                image_filename,
            )

            if event_id:
                cursor.execute(
                    """
                    UPDATE events
                    SET title=%s, description=%s, category=%s, venue=%s,
                        event_date=%s, capacity=%s, status=%s,
                        image_filename=%s
                    WHERE id=%s
                    """,
                    values + (event_id,),
                )
                flash("Event updated.", "success")
            else:
                cursor.execute(
                    """
                    INSERT INTO events
                        (title, description, category, venue, event_date,
                         capacity, status, image_filename)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
                flash("Event created.", "success")

            connection.commit()
            cursor.close()
            connection.close()
            return redirect(url_for("dashboard"))

    cursor.close()
    connection.close()
    return render_template("event_form.html", event=event)


@app.post("/admin/events/<int:event_id>/delete")
@admin_required
def delete_event(event_id):
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM events WHERE id=%s", (event_id,))
    connection.commit()
    cursor.close()
    connection.close()

    flash("Event deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/events/<int:event_id>/participants")
@admin_required
def participants(event_id):
    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events WHERE id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.execute(
        """
        SELECT s.student_no, s.full_name, s.email, s.department,
               r.registered_at
        FROM registrations r
        JOIN students s ON s.id = r.student_id
        WHERE r.event_id=%s
        ORDER BY r.registered_at DESC
        """,
        (event_id,),
    )
    students = cursor.fetchall()

    cursor.close()
    connection.close()

    if not event:
        return redirect(url_for("dashboard"))

    return render_template(
        "participants.html",
        event=event,
        students=students,
    )


@app.route("/admin/reports.csv")
@admin_required
def report():
    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.title, e.category, e.event_date, e.status,
               COUNT(r.id) AS registration_count
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        GROUP BY e.id, e.title, e.category, e.event_date, e.status
        ORDER BY e.event_date DESC
    """)
    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Event", "Category", "Date", "Status", "Registrations"]
    )

    for row in rows:
        writer.writerow([
            row["title"],
            row["category"],
            row["event_date"],
            row["status"],
            row["registration_count"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=event-report.csv"
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)