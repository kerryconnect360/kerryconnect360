
import io
import json
import os
import secrets
from datetime import datetime
from functools import wraps

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


def first_or_create_brand():
    brand = Branding.query.first()
    if not brand:
        brand = Branding()
        db.session.add(brand)
        db.session.commit()
    return brand


def ensure_initial_admin():
    if User.query.filter_by(role="admin").count() == 0:
        admin_name = os.environ.get("ADMIN_NAME", "Site Admin")
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
        admin = User(full_name=admin_name, username=admin_username, role="admin")
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()


with app.app_context():
    db.create_all()
    first_or_create_brand()
    ensure_initial_admin()
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
    if session.get("user_id"):
        user = User.query.get(session["user_id"])
    active_announcement = Announcement.query.filter_by(active=True).order_by(Announcement.created_at.desc()).first()
    return {
        "brand": brand,
        "current_user": user,
        "latest_announcement": active_announcement,
        "seat_map": VEHICLE_SEAT_MAP,
    }


@app.before_request
def load_user():
    g.current_user = None
    if session.get("user_id"):
        g.current_user = User.query.get(session["user_id"])


def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = g.current_user
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("index"))
            if not user.active:
                flash("This account is inactive.", "danger")
                return redirect(url_for("index"))
            if role and user.role != role:
                abort(403)
            return func(*args, **kwargs)
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
    open_trips = Trip.query.filter_by(status="Open").order_by(Trip.created_at.desc()).all()
    recent = open_trips[:4]
    card_url = find_brand().card_url
    return render_template("home.html", trips=recent, card_url=card_url)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/services")
def services():
    trips = Trip.query.filter_by(status="Open").order_by(Trip.departure_date.asc()).all()
    return render_template("services.html", trips=trips)


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
    available = Trip.query.filter_by(status="Open").order_by(Trip.departure_date.asc(), Trip.departure_time.asc()).all()
    return render_template("trips.html", trips=available)


@app.route("/api/trips")
def api_trips():
    rows = Trip.query.filter_by(status="Open").order_by(Trip.departure_date.asc(), Trip.departure_time.asc()).all()
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
        }
        for trip in rows
    ])


@app.route("/api/trips/<int:trip_id>/seats")
def api_trip_seats(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    if trip.status != "Open":
        return jsonify({"error": "Trip is not open"}), 404
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
    })


@app.route("/book", methods=["GET", "POST"])
def book():
    trips = Trip.query.filter_by(status="Open").order_by(Trip.departure_date.asc(), Trip.departure_time.asc()).all()
    selected_trip = None
    selected_trip_id = request.values.get("trip_id", type=int)
    if selected_trip_id:
        selected_trip = Trip.query.get(selected_trip_id)
    elif trips:
        selected_trip = trips[0]

    if request.method == "POST":
        trip_id = request.form.get("trip_id", type=int)
        trip = Trip.query.get_or_404(trip_id)
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

    return render_template("book.html", trips=trips, selected_trip=selected_trip)


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


@app.route("/board/login", methods=["GET", "POST"])
def board_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == username) | (User.username == username.lower())
        ).first()
        if user and user.role == "admin" and user.check_password(password):
            session["user_id"] = user.id
            flash("Welcome back.", "success")
            return redirect(url_for("board_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("board/login.html")


@app.route("/board/logout")
def board_logout():
    session.pop("user_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/board")
@login_required(role="admin")
def board_dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
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


@app.route("/board/users", methods=["GET", "POST"])
@login_required(role="admin")
def board_users():
    if request.method == "POST":
        user = User(
            full_name=request.form.get("full_name", "").strip(),
            username=request.form.get("username", "").strip().lower(),
            role=request.form.get("role", "driver").strip(),
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
            flash("User created.", "success")
            return redirect(url_for("board_users"))

    users = User.query.order_by(User.created_at.desc()).all()
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
    app.run(debug=True)
