
import io
import json
import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from types import SimpleNamespace

import qrcode
from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
database_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(INSTANCE_DIR, 'book_with_kerry.db')}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if database_url.startswith("sqlite"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}

db = SQLAlchemy(app)

VEHICLE_SEAT_MAP = {
    "Noah": 14,
    "Hiace": 14,
    "Shuttle": 9,
    "Van": 9,
    "Car": 4,
    "Coaster": 25,
    "Bus": 33,
    "Matatu": 14,
    "Custom": 14,
}

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
ALLOWED_CARD_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "pdf"}

ADMIN_DB_PATH = os.path.join(INSTANCE_DIR, "erom.db")


def now_utc():
    return datetime.utcnow()


class Branding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(120), nullable=False, default="Book with Kerry")
    slogan = db.Column(db.String(180), nullable=False, default="Book seats, travel smoothly.")
    about_text = db.Column(db.Text, nullable=False, default="A practical booking desk for passengers and operators.")
    support_blurb = db.Column(db.Text, nullable=False, default="Send a booking request, confirm payment, and travel with ease.")
    contact_phone = db.Column(db.String(40), nullable=False, default="0712648079")
    whatsapp_phone = db.Column(db.String(40), nullable=False, default="0712648079")
    mpesa_number = db.Column(db.String(40), nullable=False, default="0712648079")
    address = db.Column(db.String(180), nullable=False, default="Open 24/7 for bookings")
    logo_filename = db.Column(db.String(255), nullable=True)
    card_filename = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc, nullable=False)

    @property
    def logo_url(self):
        if self.logo_filename:
            return url_for("uploaded_file", filename=self.logo_filename)
        return url_for("static", filename="logo.svg")

    @property
    def card_url(self):
        if self.card_filename:
            return url_for("uploaded_file", filename=self.card_filename)
        return None


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="driver")
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(160), nullable=False)
    vehicle_name = db.Column(db.String(120), nullable=False)
    vehicle_type = db.Column(db.String(60), nullable=False, default="Noah")
    total_seats = db.Column(db.Integer, nullable=False, default=14)
    fare_per_seat = db.Column(db.Integer, nullable=False, default=0)
    departure_date = db.Column(db.String(20), nullable=False)
    departure_time = db.Column(db.String(20), nullable=True)
    origin = db.Column(db.String(120), nullable=True)
    destination = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Open")
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    driver = db.relationship("User", foreign_keys=[driver_id])
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, index=True)
    public_token = db.Column(db.String(48), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    trip = db.relationship("Trip", foreign_keys=[trip_id])
    seats_json = db.Column(db.Text, nullable=False, default="[]")
    amount = db.Column(db.Integer, nullable=False, default=0)
    mpesa_code = db.Column(db.String(80), nullable=True)
    note = db.Column(db.Text, nullable=True)
    payment_status = db.Column(db.String(40), nullable=False, default="Pending payment")
    receipt_number = db.Column(db.String(40), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)

    @property
    def seats(self):
        try:
            return json.loads(self.seats_json or "[]")
        except Exception:
            return []

    @property
    def receipt_ready(self):
        return self.payment_status == "Approved"

    @property
    def whatsapp_message(self):
        trip_label = self.trip.route_name if self.trip else "Trip"
        return (
            f"Booking {self.reference} for {self.customer_name} on {trip_label}. "
            f"Seats: {', '.join(map(str, self.seats))}. Status: {self.payment_status}."
        )


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(40), nullable=False, default="All users")
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc, nullable=False)




# --- Separate admin database (city.db) ---

def admin_db_connect():
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    conn = sqlite3.connect(ADMIN_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_admin_db():
    with admin_db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def admin_count():
    with admin_db_connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()
        return int(row["c"] or 0)


def admin_row_to_obj(row):
    if not row:
        return None
    return SimpleNamespace(
        id=row["id"],
        full_name=row["full_name"],
        username=row["username"],
        password_hash=row["password_hash"],
        active=bool(row["active"]),
        created_at=row["created_at"],
    )


def get_admin_by_id(admin_id):
    with admin_db_connect() as conn:
        row = conn.execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()
    return admin_row_to_obj(row)


def get_admin_by_username(username):
    with admin_db_connect() as conn:
        row = conn.execute("SELECT * FROM admins WHERE lower(username) = lower(?)", (username,)).fetchone()
    return admin_row_to_obj(row)


def create_admin(full_name, username, password):
    username = username.strip().lower()
    full_name = full_name.strip()
    if not full_name or not username or not password:
        return None, "Missing admin details"
    if get_admin_by_username(username):
        return None, "That admin username already exists"
    with admin_db_connect() as conn:
        conn.execute(
            "INSERT INTO admins (full_name, username, password_hash, active, created_at) VALUES (?, ?, ?, 1, ?)",
            (full_name, username, generate_password_hash(password), now_utc().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    return admin_row_to_obj(row), None


def list_admins():
    with admin_db_connect() as conn:
        rows = conn.execute("SELECT * FROM admins ORDER BY id ASC").fetchall()
    return [admin_row_to_obj(r) for r in rows]


def update_admin_active(admin_id, active):
    with admin_db_connect() as conn:
        conn.execute("UPDATE admins SET active = ? WHERE id = ?", (1 if active else 0, admin_id))
        conn.commit()
def first_or_create_brand():
    brand = Branding.query.first()
    if not brand:
        brand = Branding()
        db.session.add(brand)
        db.session.commit()
    return brand


with app.app_context():
    db.create_all()
    init_admin_db()
    first_or_create_brand()
    if Announcement.query.count() == 0:
        db.session.add(
            Announcement(
                title="Bookings are open",
                body="Request a seat, wait for payment approval, and receive a receipt after confirmation.",
                audience="All users",
            )
        )
        db.session.commit()


@app.context_processor
def inject_globals():
    brand = Branding.query.first()
    user = None
    admin = None
    if session.get("user_id"):
        user = User.query.get(session["user_id"])
    if session.get("admin_id"):
        admin = get_admin_by_id(session["admin_id"])
    active_announcement = Announcement.query.filter_by(active=True).order_by(Announcement.created_at.desc()).first()
    return {
        "brand": brand,
        "current_user": user,
        "current_admin": admin,
        "latest_announcement": active_announcement,
        "seat_map": VEHICLE_SEAT_MAP,
        "first_bookable_trip": first_bookable_trip,
        "trip_is_bookable": trip_is_bookable,
        "trip_queue_position": trip_queue_position,
        "trip_remaining_seats": trip_remaining_seats,
        "admin_count": admin_count,
    }


@app.before_request
def load_user():
    g.current_user = None
    g.current_admin = None
    if session.get("user_id"):
        g.current_user = User.query.get(session["user_id"])
    if session.get("admin_id"):
        g.current_admin = get_admin_by_id(session["admin_id"])


def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if role == "admin":
                admin = g.current_admin
                if not admin:
                    flash("Please log in first.", "warning")
                    return redirect(url_for("board_login"))
                if not admin.active:
                    flash("This admin account is inactive.", "danger")
                    return redirect(url_for("board_login"))
                return func(*args, **kwargs)
            if role == "driver":
                user = g.current_user
                if not user:
                    flash("Please log in first.", "warning")
                    return redirect(url_for("driver_login"))
                if not user.active:
                    flash("This account is inactive.", "danger")
                    return redirect(url_for("driver_login"))
                if user.role != "driver":
                    abort(403)
                return func(*args, **kwargs)
            # default: either admin or driver session may be enough
            if g.current_admin or g.current_user:
                return func(*args, **kwargs)
            flash("Please log in first.", "warning")
            return redirect(url_for("index"))
        return wrapper
    return decorator


def safe_filename_upload(file_storage, prefix="file"):
    if not file_storage or not file_storage.filename:
        return None
    name = secure_filename(file_storage.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    token = secrets.token_hex(8)
    if ext:
        final = f"{prefix}_{token}.{ext}"
    else:
        final = f"{prefix}_{token}"
    path = os.path.join(UPLOAD_DIR, final)
    file_storage.save(path)
    return final


def vehicle_capacity(vehicle_type, custom=None):
    if custom and custom > 0:
        return custom
    return VEHICLE_SEAT_MAP.get(vehicle_type, VEHICLE_SEAT_MAP["Custom"])


def all_trip_booked_seats(trip_id):
    bookings = Booking.query.filter_by(trip_id=trip_id).all()
    taken = set()
    for booking in bookings:
        if booking.payment_status != "Rejected":
            for seat in booking.seats:
                taken.add(str(seat))
    return taken


def available_seats_for_trip(trip):
    taken = all_trip_booked_seats(trip.id)
    seats = []
    for i in range(1, trip.total_seats + 1):
        label = str(i)
        seats.append({"label": label, "taken": label in taken})
    return seats


def trip_booked_count(trip):
    return len(all_trip_booked_seats(trip.id))


def trip_remaining_seats(trip):
    return max(trip.total_seats - trip_booked_count(trip), 0)


def ordered_open_trips():
    return Trip.query.filter_by(status="Open").order_by(Trip.created_at.asc(), Trip.id.asc()).all()


def first_bookable_trip():
    for trip in ordered_open_trips():
        if trip_remaining_seats(trip) > 0:
            return trip
    return None


def trip_is_bookable(trip):
    current = first_bookable_trip()
    return bool(current and trip and current.id == trip.id)


def trip_queue_position(trip):
    for idx, candidate in enumerate(ordered_open_trips(), start=1):
        if candidate.id == trip.id:
            return idx
    return None


def create_reference(prefix):
    stamp = datetime.utcnow().strftime("%Y%m%d")
    tail = secrets.token_hex(3).upper()
    return f"{prefix}-{stamp}-{tail}"


def find_brand():
    brand = Branding.query.first()
    if not brand:
        brand = first_or_create_brand()
    return brand


def require_booking_by_token(token):
    booking = Booking.query.filter_by(public_token=token).first_or_404()
    return booking


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static", "icons"), "icon-192.png")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(app.root_path, "static"), "manifest.json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(os.path.join(app.root_path, "static", "js"), "sw.js")


@app.route("/qr-code.png")
def qr_code_png():
    site_url = url_for("index", _external=True)
    img = qrcode.make(site_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@app.route("/")
def index():
    open_trips = Trip.query.filter_by(status="Open").order_by(Trip.created_at.asc(), Trip.id.asc()).all()
    bookable_trip = first_bookable_trip()
    recent = open_trips[:4]
    card_url = find_brand().card_url
    return render_template("home.html", trips=recent, card_url=card_url, bookable_trip=bookable_trip)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/services")
def services():
    trips = Trip.query.filter_by(status="Open").order_by(Trip.created_at.asc(), Trip.id.asc()).all()
    return render_template("services.html", trips=trips, bookable_trip=first_bookable_trip())


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        message = ContactMessage(
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            subject=request.form.get("subject", "").strip(),
            message=request.form.get("message", "").strip(),
        )
        if not all([message.name, message.phone, message.subject, message.message]):
            flash("Please fill every contact field.", "warning")
        else:
            db.session.add(message)
            db.session.commit()
            flash("Message sent successfully.", "success")
            return redirect(url_for("contact"))
    return render_template("contact.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/card")
def card():
    brand = find_brand()
    return render_template("card.html", brand=brand)


@app.route("/card/download")
def card_download():
    brand = find_brand()
    if not brand.card_filename:
        flash("No business card has been uploaded yet.", "warning")
        return redirect(url_for("card"))
    return send_from_directory(UPLOAD_DIR, brand.card_filename, as_attachment=True)


@app.route("/qr")
def qr():
    return render_template("qr.html")


@app.route("/trips")
def trips():
    available = Trip.query.filter_by(status="Open").order_by(Trip.created_at.asc(), Trip.id.asc()).all()
    return render_template("trips.html", trips=available, bookable_trip=first_bookable_trip())


@app.route("/api/trips")
def api_trips():
    rows = Trip.query.filter_by(status="Open").order_by(Trip.departure_date.asc(), Trip.departure_time.asc()).all()
    bookable = first_bookable_trip()
    return jsonify([
        {
            "id": trip.id,
            "route_name": trip.route_name,
            "vehicle_name": trip.vehicle_name,
            "vehicle_type": trip.vehicle_type,
            "total_seats": trip.total_seats,
            "fare_per_seat": trip.fare_per_seat,
            "departure_date": trip.departure_date,
            "departure_time": trip.departure_time,
            "origin": trip.origin,
            "destination": trip.destination,
            "available_seats": [seat["label"] for seat in available_seats_for_trip(trip) if not seat["taken"]],
            "remaining_seats": trip_remaining_seats(trip),
            "can_book": bool(bookable and bookable.id == trip.id),
            "queue_position": trip_queue_position(trip),
        }
        for trip in rows
    ])


@app.route("/api/trips/<int:trip_id>/seats")
def api_trip_seats(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    if trip.status != "Open":
        return jsonify({"error": "Trip is not open"}), 404
    current = first_bookable_trip()
    return jsonify({
        "trip": {
            "id": trip.id,
            "route_name": trip.route_name,
            "vehicle_name": trip.vehicle_name,
            "vehicle_type": trip.vehicle_type,
            "total_seats": trip.total_seats,
            "fare_per_seat": trip.fare_per_seat,
            "departure_date": trip.departure_date,
            "departure_time": trip.departure_time,
            "origin": trip.origin,
            "destination": trip.destination,
        },
        "seats": available_seats_for_trip(trip),
        "taken": sorted(list(all_trip_booked_seats(trip.id)), key=lambda x: int(x) if str(x).isdigit() else x),
        "can_book": bool(current and current.id == trip.id),
        "queue_locked": bool(current and current.id != trip.id),
        "remaining_seats": trip_remaining_seats(trip),
        "queue_position": trip_queue_position(trip),
    })


@app.route("/book", methods=["GET", "POST"])
def book():
    trips = Trip.query.filter_by(status="Open").order_by(Trip.created_at.asc(), Trip.id.asc()).all()
    bookable = first_bookable_trip()
    selected_trip = None
    selected_trip_id = request.values.get("trip_id", type=int)
    if selected_trip_id:
        candidate = Trip.query.get(selected_trip_id)
        if candidate and trip_is_bookable(candidate):
            selected_trip = candidate
        elif candidate and bookable:
            flash(f"Please book the current available vehicle first: {bookable.route_name}.", "warning")
            selected_trip = bookable
        elif candidate:
            selected_trip = candidate
    elif bookable:
        selected_trip = bookable

    if request.method == "POST":
        trip_id = request.form.get("trip_id", type=int)
        trip = Trip.query.get_or_404(trip_id)
        current = first_bookable_trip()
        if not current:
            flash("No vehicle is currently available for booking.", "warning")
            return redirect(url_for("book"))
        if trip.id != current.id:
            flash(f"Please book the current available vehicle first: {current.route_name}.", "warning")
            return redirect(url_for("book", trip_id=current.id))

        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        mpesa_code = request.form.get("mpesa_code", "").strip()
        note = request.form.get("note", "").strip()
        selected_seats = [seat.strip() for seat in request.form.get("selected_seats", "").split(",") if seat.strip()]
        if not customer_name or not phone:
            flash("Customer name and phone are required.", "warning")
            return redirect(url_for("book", trip_id=trip.id))
        if not selected_seats:
            flash("Please select at least one seat.", "warning")
            return redirect(url_for("book", trip_id=trip.id))

        taken = all_trip_booked_seats(trip.id)
        for seat in selected_seats:
            if not seat.isdigit():
                flash("Seat numbers must be numeric.", "danger")
                return redirect(url_for("book", trip_id=trip.id))
            if int(seat) < 1 or int(seat) > trip.total_seats:
                flash("One of the seats is not available on this vehicle.", "danger")
                return redirect(url_for("book", trip_id=trip.id))
            if seat in taken:
                flash(f"Seat {seat} is already booked.", "danger")
                return redirect(url_for("book", trip_id=trip.id))

        booking = Booking(
            reference=create_reference("BK"),
            public_token=secrets.token_urlsafe(18),
            customer_name=customer_name,
            phone=phone,
            trip=trip,
            seats_json=json.dumps(selected_seats),
            amount=int(len(selected_seats) * trip.fare_per_seat),
            mpesa_code=mpesa_code or None,
            note=note or None,
            payment_status="Pending payment",
        )
        db.session.add(booking)
        db.session.commit()
        flash("Booking saved. Use the booking reference to track payment and receipt status.", "success")
        return redirect(url_for("booking_success", reference=booking.reference))

    return render_template("book.html", trips=trips, selected_trip=selected_trip, bookable_trip=bookable)


@app.route("/booking/<reference>/success")
def booking_success(reference):
    booking = Booking.query.filter_by(reference=reference).first_or_404()
    return render_template("booking_success.html", booking=booking)


@app.route("/track", methods=["GET", "POST"])
def track():
    booking = None
    if request.method == "POST":
        reference = request.form.get("reference", "").strip().upper()
        phone = request.form.get("phone", "").strip()
        booking = Booking.query.filter_by(reference=reference, phone=phone).first()
        if not booking:
            flash("No booking matched those details.", "warning")
    return render_template("track.html", booking=booking)


@app.route("/receipt/<token>")
def receipt(token):
    booking = require_booking_by_token(token)
    return render_template("receipt.html", booking=booking)


@app.route("/r/<token>")
def receipt_short(token):
    return redirect(url_for("receipt", token=token))


@app.route("/erom/ger", methods=["GET", "POST"])
def erom_gate():
    exists = admin_count() > 0
    mode = request.args.get("mode", "register" if not exists else "login")
    if request.method == "POST":
        action = request.form.get("action", "register")
        if action == "register":
            if exists:
                flash("An admin already exists. Log in with your account, or use an added admin account.", "warning")
                return redirect(url_for("erom_gate", mode="login"))
            full_name = request.form.get("full_name", "").strip()
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            admin, error = create_admin(full_name, username, password)
            if error:
                flash(error, "danger")
            else:
                session["admin_id"] = admin.id
                flash("First admin created.", "success")
                return redirect(url_for("board_dashboard"))
        else:
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            admin = get_admin_by_username(username)
            if admin and admin.active:
                with admin_db_connect() as conn:
                    row = conn.execute("SELECT password_hash FROM admins WHERE id = ?", (admin.id,)).fetchone()
                if row and check_password_hash(row["password_hash"], password):
                    session["admin_id"] = admin.id
                    flash("Welcome back.", "success")
                    return redirect(url_for("board_dashboard"))
            flash("Invalid admin credentials.", "danger")
            mode = "login"
    return render_template("erom_gate.html", exists=exists, mode=mode)


@app.route("/board/register", methods=["GET", "POST"])
def board_register():
    return redirect(url_for("erom_gate", mode="register"))


@app.route("/board/login", methods=["GET", "POST"])
def board_login():
    return redirect(url_for("erom_gate", mode="login"))


@app.route("/board/logout")
def board_logout():
    session.pop("admin_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/board")
@login_required(role="admin")
def board_dashboard():
    users = User.query.filter_by(role="driver").order_by(User.created_at.desc()).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    trips = Trip.query.order_by(Trip.created_at.desc()).limit(8).all()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(4).all()
    return render_template("board/dashboard.html", users=users, bookings=bookings, trips=trips, announcements=announcements)


@app.route("/board/settings", methods=["GET", "POST"])
@login_required(role="admin")
def board_settings():
    brand = find_brand()
    if request.method == "POST":
        brand.site_name = request.form.get("site_name", brand.site_name).strip() or brand.site_name
        brand.slogan = request.form.get("slogan", brand.slogan).strip() or brand.slogan
        brand.about_text = request.form.get("about_text", brand.about_text).strip() or brand.about_text
        brand.support_blurb = request.form.get("support_blurb", brand.support_blurb).strip() or brand.support_blurb
        brand.contact_phone = request.form.get("contact_phone", brand.contact_phone).strip() or brand.contact_phone
        brand.whatsapp_phone = request.form.get("whatsapp_phone", brand.whatsapp_phone).strip() or brand.whatsapp_phone
        brand.mpesa_number = request.form.get("mpesa_number", brand.mpesa_number).strip() or brand.mpesa_number
        brand.address = request.form.get("address", brand.address).strip() or brand.address

        logo = request.files.get("logo")
        card = request.files.get("card")
        if logo and logo.filename:
            if logo.filename.rsplit(".", 1)[-1].lower() not in ALLOWED_IMAGE_EXTENSIONS:
                flash("Logo file type is not allowed.", "danger")
                return redirect(url_for("board_settings"))
            new_logo = safe_filename_upload(logo, "logo")
            brand.logo_filename = new_logo
        if card and card.filename:
            if card.filename.rsplit(".", 1)[-1].lower() not in ALLOWED_CARD_EXTENSIONS:
                flash("Business card file type is not allowed.", "danger")
                return redirect(url_for("board_settings"))
            new_card = safe_filename_upload(card, "business_card")
            brand.card_filename = new_card

        db.session.commit()
        flash("Branding updated across the site.", "success")
        return redirect(url_for("board_settings"))

    return render_template("board/settings.html", brand=brand)


@app.route("/board/admins", methods=["GET", "POST"])
@login_required(role="admin")
def board_admins():
    if request.method == "POST":
        admin, error = create_admin(
            request.form.get("full_name", ""),
            request.form.get("username", ""),
            request.form.get("password", ""),
        )
        if error:
            flash(error, "warning")
        else:
            flash("Admin created.", "success")
            return redirect(url_for("board_admins"))
    admins = list_admins()
    return render_template("board/admins.html", admins=admins)


@app.route("/board/admins/<int:admin_id>/toggle", methods=["POST"])
@login_required(role="admin")
def board_admin_toggle(admin_id):
    admins = list_admins()
    target = next((a for a in admins if a.id == admin_id), None)
    if not target:
        abort(404)
    active_admins = [a for a in admins if a.active]
    if target.id == g.current_admin.id and len(active_admins) <= 1 and target.active:
        flash("Keep at least one active admin account.", "warning")
        return redirect(url_for("board_admins"))
    update_admin_active(admin_id, not target.active)
    flash("Admin account updated.", "success")
    return redirect(url_for("board_admins"))


@app.route("/board/users", methods=["GET", "POST"])
@login_required(role="admin")
def board_users():
    if request.method == "POST":
        user = User(
            full_name=request.form.get("full_name", "").strip(),
            username=request.form.get("username", "").strip().lower(),
            role="driver",
            active=True,
        )
        password = request.form.get("password", "")
        if not all([user.full_name, user.username, password]):
            flash("Name, username, and password are required.", "warning")
        elif User.query.filter_by(username=user.username).first():
            flash("That username already exists.", "warning")
        else:
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Driver created.", "success")
            return redirect(url_for("board_users"))

    users = User.query.filter_by(role="driver").order_by(User.created_at.desc()).all()
    return render_template("board/users.html", users=users)


@app.route("/board/users/<int:user_id>/toggle", methods=["POST"])
@login_required(role="admin")
def board_user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Admin accounts cannot be disabled here.", "warning")
        return redirect(url_for("board_users"))
    user.active = not user.active
    db.session.commit()
    flash("User status updated.", "success")
    return redirect(url_for("board_users"))


@app.route("/board/trips", methods=["GET", "POST"])
@login_required(role="admin")
def board_trips():
    if request.method == "POST":
        vehicle_type = request.form.get("vehicle_type", "Noah")
        custom_seats = request.form.get("total_seats", type=int)
        trip = Trip(
            route_name=request.form.get("route_name", "").strip(),
            vehicle_name=request.form.get("vehicle_name", "").strip(),
            vehicle_type=vehicle_type,
            total_seats=vehicle_capacity(vehicle_type, custom_seats),
            fare_per_seat=request.form.get("fare_per_seat", type=int) or 0,
            departure_date=request.form.get("departure_date", "").strip(),
            departure_time=request.form.get("departure_time", "").strip(),
            origin=request.form.get("origin", "").strip(),
            destination=request.form.get("destination", "").strip(),
            notes=request.form.get("notes", "").strip(),
            status=request.form.get("status", "Open").strip(),
        )
        driver_id = request.form.get("driver_id", type=int)
        if driver_id:
            trip.driver_id = driver_id
        if not all([trip.route_name, trip.vehicle_name, trip.departure_date]):
            flash("Route name, vehicle name, and departure date are required.", "warning")
        else:
            db.session.add(trip)
            db.session.commit()
            flash("Trip created.", "success")
            return redirect(url_for("board_trips"))

    trips = Trip.query.order_by(Trip.created_at.desc()).all()
    drivers = User.query.filter_by(role="driver", active=True).order_by(User.full_name.asc()).all()
    return render_template("board/trips.html", trips=trips, drivers=drivers, vehicle_map=VEHICLE_SEAT_MAP)


@app.route("/board/trips/<int:trip_id>/delete", methods=["POST"])
@login_required(role="admin")
def board_trip_delete(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    db.session.delete(trip)
    db.session.commit()
    flash("Trip deleted.", "success")
    return redirect(url_for("board_trips"))


@app.route("/board/bookings")
@login_required(role="admin")
def board_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    trips = Trip.query.order_by(Trip.created_at.desc()).all()
    drivers = User.query.filter_by(role="driver", active=True).order_by(User.full_name.asc()).all()
    return render_template("board/bookings.html", bookings=bookings, trips=trips, drivers=drivers)


@app.route("/board/bookings/<int:booking_id>/approve", methods=["POST"])
@login_required(role="admin")
def board_booking_approve(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.payment_status = "Approved"
    booking.receipt_number = booking.receipt_number or create_reference("RCPT")
    booking.approved_at = now_utc()
    booking.approved_by_id = g.current_user.id
    db.session.commit()
    flash("Payment approved and receipt unlocked.", "success")
    return redirect(url_for("board_bookings"))


@app.route("/board/bookings/<int:booking_id>/reject", methods=["POST"])
@login_required(role="admin")
def board_booking_reject(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.payment_status = "Rejected"
    db.session.commit()
    flash("Booking marked as rejected.", "success")
    return redirect(url_for("board_bookings"))


@app.route("/board/bookings/<int:booking_id>/assign", methods=["POST"])
@login_required(role="admin")
def board_booking_assign(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    trip_id = request.form.get("trip_id", type=int)
    if trip_id:
        booking.trip_id = trip_id
        db.session.commit()
        flash("Booking reassigned.", "success")
    return redirect(url_for("board_bookings"))


@app.route("/board/announcements", methods=["GET", "POST"])
@login_required(role="admin")
def board_announcements():
    if request.method == "POST":
        ann = Announcement(
            title=request.form.get("title", "").strip(),
            body=request.form.get("body", "").strip(),
            audience=request.form.get("audience", "All users").strip(),
            active=True,
        )
        if not ann.title or not ann.body:
            flash("Title and body are required.", "warning")
        else:
            db.session.add(ann)
            db.session.commit()
            flash("Announcement published.", "success")
            return redirect(url_for("board_announcements"))

    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("board/announcements.html", announcements=items)


@app.route("/board/announcements/<int:ann_id>/toggle", methods=["POST"])
@login_required(role="admin")
def board_announcement_toggle(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    ann.active = not ann.active
    db.session.commit()
    flash("Announcement updated.", "success")
    return redirect(url_for("board_announcements"))


@app.route("/drivers/login", methods=["GET", "POST"])
def driver_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, role="driver").first()
        if user and user.active and user.check_password(password):
            session["user_id"] = user.id
            flash("Driver login successful.", "success")
            return redirect(url_for("driver_dashboard"))
        flash("Invalid driver credentials.", "danger")
    return render_template("drivers/login.html")


@app.route("/drivers/logout")
def driver_logout():
    session.pop("user_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/drivers")
@login_required(role="driver")
def driver_dashboard():
    my_trips = Trip.query.filter_by(driver_id=g.current_user.id).order_by(Trip.created_at.desc()).all()
    assigned_bookings = Booking.query.join(Trip).filter(Trip.driver_id == g.current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template("drivers/dashboard.html", trips=my_trips, bookings=assigned_bookings)


@app.route("/drivers/trips", methods=["GET", "POST"])
@login_required(role="driver")
def driver_trips():
    if request.method == "POST":
        vehicle_type = request.form.get("vehicle_type", "Noah")
        custom_seats = request.form.get("total_seats", type=int)
        trip = Trip(
            route_name=request.form.get("route_name", "").strip(),
            vehicle_name=request.form.get("vehicle_name", "").strip(),
            vehicle_type=vehicle_type,
            total_seats=vehicle_capacity(vehicle_type, custom_seats),
            fare_per_seat=request.form.get("fare_per_seat", type=int) or 0,
            departure_date=request.form.get("departure_date", "").strip(),
            departure_time=request.form.get("departure_time", "").strip(),
            origin=request.form.get("origin", "").strip(),
            destination=request.form.get("destination", "").strip(),
            notes=request.form.get("notes", "").strip(),
            status="Open",
            driver_id=g.current_user.id,
        )
        if not all([trip.route_name, trip.vehicle_name, trip.departure_date]):
            flash("Route name, vehicle name, and departure date are required.", "warning")
        else:
            db.session.add(trip)
            db.session.commit()
            flash("Trip created and published.", "success")
            return redirect(url_for("driver_trips"))

    trips = Trip.query.filter_by(driver_id=g.current_user.id).order_by(Trip.created_at.desc()).all()
    return render_template("drivers/trips.html", trips=trips, vehicle_map=VEHICLE_SEAT_MAP)


@app.route("/drivers/bookings/<int:booking_id>/update", methods=["POST"])
@login_required(role="driver")
def driver_booking_update(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.trip.driver_id != g.current_user.id:
        abort(403)
    status = request.form.get("payment_status", booking.payment_status)
    booking.payment_status = status
    db.session.commit()
    flash("Trip booking updated.", "success")
    return redirect(url_for("driver_dashboard"))


@app.errorhandler(404)
def handle_404(_):
    return render_template("404.html"), 404


@app.errorhandler(403)
def handle_403(_):
    return "Forbidden", 403

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5003)),
        debug=True
    )
