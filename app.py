
from datetime import datetime
import os
import random
import secrets
from functools import wraps
from pathlib import Path

from flask import (
    Flask, flash, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_URL = os.environ.get('DATABASE_URL')
if DB_URL and DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'change-me-now'),
    SQLALCHEMY_DATABASE_URI=DB_URL or f"sqlite:///{BASE_DIR / 'book_with_kerrie.db'}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
)

STATIC_DIR = BASE_DIR / 'static'
UPLOAD_DIR = STATIC_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_SLUG = os.environ.get('ADMIN_SLUG', 'xtspolsjhulupjoppsup-lmkzcodup')
DRIVER_SLUG = os.environ.get('DRIVER_SLUG', 'drive-hub')


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'ops_entry'


class Admin(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    license_no = db.Column(db.String(80), nullable=False)
    login_name = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.String(20), nullable=False, default='4.9')
    status = db.Column(db.String(20), nullable=False, default='Available')
    operator_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    plate_no = db.Column(db.String(40), nullable=False, unique=True)
    category = db.Column(db.String(60), nullable=False)
    seats = db.Column(db.Integer, nullable=False, default=4)
    color = db.Column(db.String(40), nullable=False, default='Pearl White')
    status = db.Column(db.String(20), nullable=False, default='Available')
    operator_name = db.Column(db.String(120), nullable=False, default='Kerrie Fleet')
    rating = db.Column(db.String(20), nullable=False, default='4.9')
    priority_score = db.Column(db.Integer, nullable=False, default=50)
    driver_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    pickup = db.Column(db.String(255), nullable=False)
    dropoff = db.Column(db.String(255), nullable=False)
    preferred_operator = db.Column(db.String(120), nullable=True)
    vehicle_type = db.Column(db.String(60), nullable=False)
    passengers = db.Column(db.Integer, nullable=False, default=1)
    journey_date = db.Column(db.String(30), nullable=False)
    journey_time = db.Column(db.String(30), nullable=False)
    luggage = db.Column(db.String(40), nullable=False, default='Light')
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Pending')
    assigned_driver = db.Column(db.String(120), nullable=True)
    assigned_vehicle = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))



def ops_only(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(*args, **kwargs):
        if not isinstance(current_user, Admin):
            flash('Admin access required.', 'error')
            return redirect(url_for('ops_entry'))
        return view_func(*args, **kwargs)

    return wrapper

def driver_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('driver_id'):
            return redirect(url_for('driver_login'))
        return view(*args, **kwargs)
    return wrapped


def get_setting(key: str, default: str = '') -> str:
    record = SiteSetting.query.filter_by(key=key).first()
    return record.value if record else default


def upsert_setting(key: str, value: str) -> None:
    record = SiteSetting.query.filter_by(key=key).first()
    if record is None:
        record = SiteSetting(key=key, value=value)
        db.session.add(record)
    else:
        record.value = value


def parse_rating(value, default=4.8):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def save_upload(file_storage, prefix: str) -> str:
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return ''
    filename = secure_filename(file_storage.filename)
    suffix = Path(filename).suffix.lower() or '.png'
    out_name = f"{prefix}_{secrets.token_hex(4)}{suffix}"
    out_path = UPLOAD_DIR / out_name
    file_storage.save(out_path)
    return f'uploads/{out_name}'


def setup_defaults():
    if not SiteSetting.query.first():
        for key, value in {
            'brand_name': 'Book with Kerrie',
            'brand_tagline': 'Elegant booking for calm, fast transport handoffs.',
            'support_phone': '254 712 648079',
            'support_email': 'support@kerrie.co.ke',
            'about_text': 'Kerrie is a private transport desk for vehicles, drivers, and dispatch-ready bookings.',
            'business_card_text': 'Book with Kerrie · Private transport reservations · Dispatch support',
            'qr_label': 'Scan for booking desk',
            'public_ui_style': 'ig_bottom',
            'brand_logo_file': '',
            'business_card_file': '',
        }.items():
            db.session.add(SiteSetting(key=key, value=value))

    if not Vehicle.query.first():
        db.session.add_all([
            Vehicle(name='Noah Premium Shuttle', plate_no='KRR-204A', category='Executive Shuttle', seats=14, color='Pearl White', operator_name='Noah Cars', rating='4.9', priority_score=92, driver_name='Noah M.'),
            Vehicle(name='Kerrie Urban Black', plate_no='KRR-811B', category='Premium Sedan', seats=4, color='Midnight Black', operator_name='Kerrie Fleet', rating='5.0', priority_score=96, driver_name='Amina W.'),
            Vehicle(name='City Glide SUV', plate_no='KRR-550C', category='SUV', seats=6, color='Sunlit Silver', operator_name='City Glide', rating='4.8', priority_score=84, driver_name='Brian O.'),
        ])
    if not Driver.query.first():
        sample_drivers = [
            ('Amina Wairimu', '+254700111222', 'DL-10294', 'amina.wairimu', 'Amina@2026', '4.9', 'Kerrie Fleet'),
            ('Peter Kamau', '+254700333444', 'DL-11887', 'peter.kamau', 'Peter@2026', '5.0', 'Kerrie Fleet'),
            ('Brian Odhiambo', '+254700555666', 'DL-12051', 'brian.odhiambo', 'Brian@2026', '4.8', 'City Glide'),
        ]
        for full_name, phone, license_no, login_name, password, rating, operator_name in sample_drivers:
            d = Driver(full_name=full_name, phone=phone, license_no=license_no, login_name=login_name, rating=rating, operator_name=operator_name)
            d.set_password(password)
            db.session.add(d)
    db.session.commit()


@app.before_request
def init_db():
    db.create_all()
    if not SiteSetting.query.first() or not Vehicle.query.first() or not Driver.query.first():
        setup_defaults()


def public_vehicle_cards(preferred_operator: str = '', passengers: int = 0, vehicle_type: str = ''):
    vehicles = Vehicle.query.filter(Vehicle.status != 'Maintenance').all()
    preferred_operator = (preferred_operator or '').strip().lower()
    vehicle_type = (vehicle_type or '').strip().lower()

    def score(vehicle: Vehicle):
        rating = parse_rating(vehicle.rating)
        total = int(vehicle.priority_score or 0) * 10 + int(rating * 100)
        if preferred_operator and preferred_operator == (vehicle.operator_name or '').lower():
            total += 250
        if vehicle_type and vehicle_type in (vehicle.category or '').lower():
            total += 140
        if passengers:
            if vehicle.seats >= passengers:
                total += 80 + min(vehicle.seats - passengers, 12)
            else:
                total -= 80 + (passengers - vehicle.seats) * 8
        total += random.randint(0, 18)
        return total

    return sorted(vehicles, key=score, reverse=True)[:3]


def assign_vehicle_to_booking(preferred_operator: str, vehicle_type: str, passengers: int):
    vehicles = public_vehicle_cards(preferred_operator=preferred_operator, passengers=passengers, vehicle_type=vehicle_type)
    for vehicle in vehicles:
        if vehicle.status == 'Available':
            return vehicle.name, vehicle.driver_name or 'Dispatch team'
    if vehicles:
        return vehicles[0].name, vehicles[0].driver_name or 'Dispatch team'
    return None, None


@app.route('/')
def landing():
    settings = {k: get_setting(k, '') for k in [
        'brand_name', 'brand_tagline', 'support_phone', 'support_email',
        'about_text', 'business_card_text', 'qr_label', 'public_ui_style', 'brand_logo_file', 'business_card_file'
    ]}
    settings.setdefault('brand_name', 'Book with Kerrie')
    settings.setdefault('brand_tagline', 'Elegant booking for calm, fast transport handoffs.')
    settings.setdefault('support_phone', '254 712 648079')
    settings.setdefault('support_email', 'support@kerrie.co.ke')

    vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    ratings = []
    seen = set()
    for item in vehicles:
        label = item.operator_name or item.name
        if label in seen:
            continue
        ratings.append({'label': label, 'rating': item.rating})
        seen.add(label)
        if len(ratings) == 3:
            break
    if not ratings:
        ratings = [
            {'label': 'Kerrie Fleet', 'rating': '5.0'},
            {'label': 'Noah Cars', 'rating': '4.9'},
            {'label': 'City Glide', 'rating': '4.8'},
        ]

    categories = sorted({vehicle.category for vehicle in vehicles})
    operators = sorted({vehicle.operator_name for vehicle in vehicles})
    return render_template(
        'landing.html',
        settings=settings,
        ratings=ratings,
        categories=categories,
        operators=operators,
        preferred_operator=request.args.get('operator', ''),
        preferred_vehicle_type=request.args.get('type', ''),
        preferred_passengers=request.args.get('passengers', '1'),
        public_ui_style=get_setting('public_ui_style', 'ig_bottom'),
    )


@app.route('/booking', methods=['POST'])
def create_booking():
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip() or None
    pickup = request.form.get('pickup', '').strip()
    dropoff = request.form.get('dropoff', '').strip()
    preferred_operator = request.form.get('preferred_operator', '').strip()
    vehicle_type = request.form.get('vehicle_type', '').strip()
    passengers = int(request.form.get('passengers', 1) or 1)
    journey_date = request.form.get('journey_date', '').strip()
    journey_time = request.form.get('journey_time', '').strip()
    luggage = request.form.get('luggage', 'Light').strip()
    notes = request.form.get('notes', '').strip() or None

    if not all([full_name, phone, pickup, dropoff, vehicle_type, journey_date, journey_time]):
        flash('Please complete the booking details.', 'error')
        return redirect(url_for('landing'))

    assigned_vehicle, assigned_driver = assign_vehicle_to_booking(preferred_operator or '', vehicle_type, passengers)
    reference = f"KERRIE-{secrets.token_hex(3).upper()}"
    booking = Booking(
        reference=reference,
        full_name=full_name,
        phone=phone,
        email=email,
        pickup=pickup,
        dropoff=dropoff,
        preferred_operator=preferred_operator,
        vehicle_type=vehicle_type,
        passengers=passengers,
        journey_date=journey_date,
        journey_time=journey_time,
        luggage=luggage,
        notes=notes,
        assigned_vehicle=assigned_vehicle,
        assigned_driver=assigned_driver,
    )
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for('receipt', reference=reference))


@app.route('/receipt/<reference>')
def receipt(reference):
    booking = Booking.query.filter_by(reference=reference).first_or_404()
    settings = {
        'brand_name': get_setting('brand_name', 'Book with Kerrie'),
        'support_phone': get_setting('support_phone', '254 712 648079'),
    }
    return render_template('booking_detail.html', booking=booking, settings=settings)


@app.route('/ops')
def ops_entry():
    admin_count = Admin.query.count()
    return render_template('admin/login.html', setup_mode=admin_count == 0, admin_path=url_for('ops_secret'))


@app.route(f'/{ADMIN_SLUG}', methods=['GET', 'POST'])
def ops_secret():
    admin_count = Admin.query.count()
    setup_mode = admin_count == 0
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        if setup_mode:
            if not all([full_name, email, password]):
                flash('Complete the first admin setup.', 'error')
                return redirect(url_for('ops_secret'))
            if Admin.query.filter_by(email=email).first():
                flash('Email already exists.', 'error')
                return redirect(url_for('ops_secret'))
            admin = Admin(full_name=full_name, email=email, phone=phone or None)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            login_user(admin)
            flash('First admin created.', 'success')
            return redirect(url_for('ops_dashboard'))

        user = Admin.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Access not recognized.', 'error')
            return redirect(url_for('ops_secret'))
        login_user(user)
        return redirect(url_for('ops_dashboard'))
    return render_template('admin/login.html', setup_mode=setup_mode, admin_path=url_for('ops_secret'))


@app.route(f'/{ADMIN_SLUG}/logout')
@login_required
def ops_logout():
    logout_user()
    return redirect(url_for('landing'))


@app.route(f'/{ADMIN_SLUG}/dashboard')
@login_required
@ops_only
def ops_dashboard():
    stats = {
        'bookings': Booking.query.count(),
        'pending': Booking.query.filter_by(status='Pending').count(),
        'confirmed': Booking.query.filter_by(status='Confirmed').count(),
        'drivers': Driver.query.count(),
        'vehicles': Vehicle.query.count(),
        'admins': Admin.query.count(),
    }
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(6).all()
    settings = {k: get_setting(k, '') for k in ['brand_name', 'brand_logo_file', 'business_card_file', 'business_card_text']}
    return render_template('admin/dashboard.html', stats=stats, bookings=bookings, settings=settings)


@app.route(f'/{ADMIN_SLUG}/bookings')
@login_required
@ops_only
def ops_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    drivers = Driver.query.order_by(Driver.created_at.asc()).all()
    vehicles = Vehicle.query.order_by(Vehicle.created_at.asc()).all()
    return render_template('admin/bookings.html', bookings=bookings, drivers=drivers, vehicles=vehicles)


@app.route(f'/{ADMIN_SLUG}/bookings/<int:booking_id>/update', methods=['POST'])
@login_required
@ops_only
def ops_booking_update(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('ops_bookings'))
    booking.status = request.form.get('status', booking.status)
    booking.assigned_driver = request.form.get('assigned_driver', booking.assigned_driver)
    booking.assigned_vehicle = request.form.get('assigned_vehicle', booking.assigned_vehicle)
    db.session.commit()
    flash('Booking updated.', 'success')
    return redirect(url_for('ops_bookings'))


@app.route(f'/{ADMIN_SLUG}/drivers', methods=['GET', 'POST'])
@login_required
@ops_only
def ops_drivers():
    if request.method == 'POST':
        login_name = request.form.get('login_name', '').strip().lower() or request.form.get('full_name', '').strip().lower().replace(' ', '.')
        password = request.form.get('password', '')
        if not login_name or not password:
            flash('Driver login name and password are required.', 'error')
            return redirect(url_for('ops_drivers'))
        if Driver.query.filter_by(login_name=login_name).first():
            flash('Driver login already exists.', 'error')
            return redirect(url_for('ops_drivers'))
        driver = Driver(
            full_name=request.form.get('full_name', '').strip(),
            phone=request.form.get('phone', '').strip(),
            license_no=request.form.get('license_no', '').strip(),
            rating=request.form.get('rating', '4.9').strip(),
            status=request.form.get('status', 'Available').strip(),
            operator_name=request.form.get('operator_name', '').strip() or None,
            login_name=login_name,
        )
        driver.set_password(password)
        db.session.add(driver)
        db.session.commit()
        flash('Driver added.', 'success')
        return redirect(url_for('ops_drivers'))
    drivers = Driver.query.order_by(Driver.created_at.desc()).all()
    return render_template('admin/drivers.html', drivers=drivers)


@app.route(f'/{ADMIN_SLUG}/vehicles', methods=['GET', 'POST'])
@login_required
@ops_only
def ops_vehicles():
    if request.method == 'POST':
        db.session.add(Vehicle(
            name=request.form.get('name', '').strip(),
            plate_no=request.form.get('plate_no', '').strip(),
            category=request.form.get('category', '').strip(),
            seats=int(request.form.get('seats', 4) or 4),
            color=request.form.get('color', 'Pearl White').strip(),
            status=request.form.get('status', 'Available').strip(),
            operator_name=request.form.get('operator_name', '').strip() or 'Kerrie Fleet',
            rating=request.form.get('rating', '4.9').strip(),
            priority_score=int(request.form.get('priority_score', 50) or 50),
            driver_name=request.form.get('driver_name', '').strip() or None,
        ))
        db.session.commit()
        flash('Vehicle added.', 'success')
        return redirect(url_for('ops_vehicles'))
    vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    return render_template('admin/vehicles.html', vehicles=vehicles)


@app.route(f'/{ADMIN_SLUG}/admins', methods=['GET', 'POST'])
@login_required
@ops_only
def ops_admins():
    if request.method == 'POST':
        admin = Admin(
            full_name=request.form.get('full_name', '').strip(),
            email=request.form.get('email', '').strip().lower(),
            phone=request.form.get('phone', '').strip() or None,
        )
        password = request.form.get('password', '')
        if not all([admin.full_name, admin.email, password]):
            flash('Complete all admin fields.', 'error')
            return redirect(url_for('ops_admins'))
        if Admin.query.filter_by(email=admin.email).first():
            flash('Email already exists.', 'error')
            return redirect(url_for('ops_admins'))
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        flash('New admin created.', 'success')
        return redirect(url_for('ops_admins'))
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template('admin/admins.html', admins=admins)


@app.route(f'/{ADMIN_SLUG}/settings', methods=['GET', 'POST'])
@login_required
@ops_only
def ops_settings():
    keys = ['brand_name', 'brand_tagline', 'support_phone', 'support_email', 'about_text', 'business_card_text', 'qr_label', 'public_ui_style', 'brand_logo_file', 'business_card_file']
    if request.method == 'POST':
        for key in keys[:-2]:
            upsert_setting(key, request.form.get(key, '').strip())
        logo_path = save_upload(request.files.get('brand_logo'), 'brand_logo')
        card_path = save_upload(request.files.get('business_card_image'), 'business_card')
        if logo_path:
            upsert_setting('brand_logo_file', logo_path)
        if card_path:
            upsert_setting('business_card_file', card_path)
        db.session.commit()
        flash('Settings updated.', 'success')
        return redirect(url_for('ops_settings'))
    settings = {key: get_setting(key, '') for key in keys}
    return render_template('admin/settings.html', admin=current_user, settings=settings)


@app.route('/driver', methods=['GET', 'POST'])
def driver_login():
    if request.method == 'POST':
        login_name = request.form.get('login_name', '').strip().lower()
        password = request.form.get('password', '')
        driver = Driver.query.filter_by(login_name=login_name).first()
        if not driver or not driver.check_password(password):
            flash('Driver login not recognized.', 'error')
            return redirect(url_for('driver_login'))
        session['driver_id'] = driver.id
        session['driver_name'] = driver.full_name
        return redirect(url_for('driver_dashboard'))
    return render_template('driver/login.html')


@app.route('/driver/logout')
def driver_logout():
    session.pop('driver_id', None)
    session.pop('driver_name', None)
    return redirect(url_for('landing'))


@app.route('/driver/dashboard')
@driver_required
def driver_dashboard():
    driver = db.session.get(Driver, int(session['driver_id']))
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(6).all()
    return render_template('driver/dashboard.html', driver=driver, bookings=bookings)


@app.route('/manifest.webmanifest')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.webmanifest')


@app.route('/sw.js')
def service_worker():
    return send_from_directory(app.static_folder, 'sw.js')


@app.route('/offline')
def offline():
    return render_template('offline.html')


@app.route('/api/summary')
def api_summary():
    return jsonify({
        'vehicles': Vehicle.query.count(),
        'drivers': Driver.query.count(),
        'bookings': Booking.query.count(),
        'admins': Admin.query.count(),
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not SiteSetting.query.first() or not Vehicle.query.first() or not Driver.query.first():
            setup_defaults()
    app.run(debug=True)
