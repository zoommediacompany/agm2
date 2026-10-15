from functools import wraps
import csv
import io
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

from flask import Flask, Response, flash, g, redirect, render_template, request, send_file, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
# On Vercel, app.py is imported from api/index.py so __file__ is in the project root already.
# Guard against being called from a subdirectory.
if not (BASE_DIR / "index.html").exists() and (BASE_DIR.parent / "index.html").exists():
    BASE_DIR = BASE_DIR.parent
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_iKNPMVkn5xQ3@ep-royal-glitter-avibi1x2-pooler.c-11.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
UPLOAD_FOLDER = Path("/tmp") / "uploads" if os.environ.get("VERCEL") == "1" else BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
PARTNER_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("WILD_SECRET_KEY", "local-development-key"),
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    DATABASE_URL=DATABASE_URL,
)
UPLOAD_FOLDER.mkdir(exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        g.db.autocommit = True
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    program TEXT NOT NULL,
                    document_name TEXT,
                    privacy_consent INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'New',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS partners (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    partner_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    website TEXT,
                    description TEXT,
                    logo_name TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        db.commit()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def home():
    return send_file(BASE_DIR / "pages" / "travel.html")


@app.route("/images/<path:filename>")
def image_file(filename):
    return send_from_directory(BASE_DIR / "images", filename)


@app.route("/programs")
def programs():
    return send_file(BASE_DIR / "pages" / "programs.html")


@app.route("/expeditions")
def expeditions():
    return send_file(BASE_DIR / "pages" / "programs.html")


@app.route("/universities")
def universities():
    return send_file(BASE_DIR / "pages" / "universities.html")


@app.route("/exchange")
def exchange():
    return send_file(BASE_DIR / "pages" / "universities.html")


@app.route("/build-my-wild")
def build_my_wild():
    return send_file(BASE_DIR / "pages" / "travel.html")


@app.route("/students")
def students():
    return send_file(BASE_DIR / "pages" / "students.html")


@app.route("/travel")
def travel():
    return send_file(BASE_DIR / "pages" / "travel.html")


@app.route("/about")
def about():
    return send_file(BASE_DIR / "pages" / "about.html")


@app.route("/contact")
def contact():
    return send_file(BASE_DIR / "pages" / "contact.html")


@app.route("/safety")
def safety():
    return send_file(BASE_DIR / "pages" / "safety.html")


@app.route("/why-wild")
def why_wild():
    return send_file(BASE_DIR / "pages" / "safety.html")


@app.route("/destinations")
def destinations():
    return send_file(BASE_DIR / "pages" / "destinations.html")


@app.route("/journal")
def journal():
    return send_file(BASE_DIR / "pages" / "safety.html")


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        program = request.form.get("program", "").strip()
        privacy_consent = request.form.get("privacy_consent") == "on"
        document = request.files.get("resume")

        if not all((name, email, phone, program)):
            flash("Please complete every required field.", "error")
        elif not privacy_consent:
            flash("Please accept the privacy notice before submitting.", "error")
        elif document and document.filename and not allowed_file(document.filename):
            flash("Upload a PDF, DOC, or DOCX file.", "error")
        else:
            document_name = None
            if document and document.filename:
                document_name = secure_filename(document.filename)
                document.save(UPLOAD_FOLDER / document_name)

            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO applications (name, email, phone, program, document_name, privacy_consent) VALUES (%s, %s, %s, %s, %s, %s)",
                    (name, email, phone, program, document_name, int(privacy_consent)),
                )
            db.commit()
            return render_template("application_success.html", name=name)

    return render_template("application.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        expected_password = os.environ.get("WILD_ADMIN_PASSWORD", "admin")
        if request.form.get("password") == expected_password:
            session["admin_authenticated"] = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("The password is incorrect.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    status = request.args.get("status", "All")
    search = request.args.get("search", "").strip()
    query = "SELECT * FROM applications WHERE 1 = 1"
    params = []

    if status != "All":
        query += " AND status = %s"
        params.append(status)
    if search:
        query += " AND (name ILIKE %s OR email ILIKE %s OR program ILIKE %s)"
        term = f"%{search}%"
        params.extend((term, term, term))
    query += " ORDER BY created_at DESC"

    db = get_db()
    with db.cursor() as cur:
        cur.execute(query, params)
        applications = cur.fetchall()
        cur.execute("SELECT status, COUNT(*) AS count FROM applications GROUP BY status")
        counts = {row["status"]: row["count"] for row in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM partners")
        partner_count = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM applications WHERE created_at >= NOW() - INTERVAL '7 days'"
        )
        recent_count = cur.fetchone()[0]
    return render_template(
        "admin_dashboard.html",
        applications=applications,
        counts=counts,
        total_count=sum(counts.values()),
        partner_count=partner_count,
        recent_count=recent_count,
        active_status=status,
        search=search,
    )


@app.get("/admin/export/applications")
@admin_required
def export_applications():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, name, email, phone, program, document_name, status, created_at FROM applications ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("ID", "Name", "Email", "Phone", "Program", "Document", "Status", "Submitted"))
    writer.writerows(tuple(row.values()) for row in rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=wild-applications.csv"},
    )


@app.route("/admin/partners", methods=["GET", "POST"])
@admin_required
def admin_partners():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        partner_type = request.form.get("partner_type", "").strip()
        country = request.form.get("country", "").strip()
        website = request.form.get("website", "").strip()
        description = request.form.get("description", "").strip()
        logo = request.files.get("logo")

        if not all((name, partner_type, country)):
            flash("Name, partner type, and country are required.", "error")
        elif logo and logo.filename and ("." not in logo.filename or logo.filename.rsplit(".", 1)[1].lower() not in PARTNER_LOGO_EXTENSIONS):
            flash("Upload a PNG, JPG, WEBP, or SVG logo file.", "error")
        else:
            logo_name = None
            if logo and logo.filename:
                logo_name = secure_filename(logo.filename)
                logo.save(UPLOAD_FOLDER / logo_name)
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO partners (name, partner_type, country, website, description, logo_name) VALUES (%s, %s, %s, %s, %s, %s)",
                    (name, partner_type, country, website, description, logo_name),
                )
            db.commit()
            return redirect(url_for("admin_partners"))

    with db.cursor() as cur:
        cur.execute("SELECT * FROM partners ORDER BY created_at DESC")
        partners = cur.fetchall()
    return render_template("admin_partners.html", partners=partners)


@app.post("/admin/applications/<int:application_id>/status")
@admin_required
def update_status(application_id):
    new_status = request.form.get("status")
    if new_status in {"New", "Reviewing", "Approved", "Rejected"}:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "UPDATE applications SET status = %s WHERE id = %s",
                (new_status, application_id),
            )
        db.commit()
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.errorhandler(413)
def request_too_large(_error):
    flash("That document is too large. The maximum size is 8 MB.", "error")
    return redirect(url_for("apply"))


try:
    init_db()
except Exception as _db_init_err:
    import warnings
    warnings.warn(f"Database init skipped: {_db_init_err}")

if __name__ == "__main__":
    app.run(debug=True)
