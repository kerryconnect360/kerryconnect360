import os
from datetime import datetime
from functools import wraps
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key')
db_url = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(INSTANCE_DIR, 'city_connect.db')}")
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if db_url.startswith('sqlite'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'check_same_thread': False}}


db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, default=lambda: f'CC-{uuid4().hex[:8].upper()}')
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    pickup = db.Column(db.String(120), nullable=False)
    dropoff = db.Column(db.String(120), nullable=False)
    travel_date = db.Column(db.String(30), nullable=False)
    travel_time = db.Column(db.String(30), nullable=True)
    passengers = db.Column(db.Integer, default=1, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Pending')
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    assigned_driver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assigned_driver = db.relationship('User', foreign_keys=[assigned_driver_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(30), nullable=False, default='All users')
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        default_name = os.environ.get('ADMIN_NAME', 'Site Admin')
        default_email = os.environ.get('ADMIN_EMAIL', 'admin@cityconnect.local')
        default_password = os.environ.get('ADMIN_PASSWORD', 'Admin123!')
        admin = User(full_name=default_name, email=default_email.lower(), role='admin')
        admin.set_password(default_password)
        db.session.add(admin)
        db.session.commit()


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('board_login'))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for('board_login'))
        if user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped


def driver_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for('drivers_login'))
        if user.role != 'driver':
            flash('Driver access required.', 'error')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        'current_user': user,
        'is_admin': bool(user and user.role == 'admin'),
        'is_driver': bool(user and user.role == 'driver'),
        'user_count': User.query.count(),
        'driver_count': User.query.filter_by(role='driver').count(),
        'booking_count': Booking.query.count(),
        'announcement_count': Announcement.query.filter_by(active=True).count(),
        'year': datetime.utcnow().year,
        'latest_announcement': Announcement.query.filter_by(active=True).order_by(Announcement.created_at.desc()).first(),
    }


@app.route('/')
def index():
    return render_template(
        'home.html',
        recent_bookings=Booking.query.order_by(Booking.created_at.desc()).limit(3).all(),
        active_announcements=Announcement.query.filter_by(active=True).order_by(Announcement.created_at.desc()).limit(2).all(),
    )


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not name or not email or not subject or not message:
            flash('Please fill all contact fields.', 'error')
        else:
            db.session.add(ContactMessage(name=name, email=email, subject=subject, message=message))
            db.session.commit()
            flash('Thank you. Your message has been sent.', 'success')
            return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone', '').strip()
        pickup = request.form.get('pickup', '').strip()
        dropoff = request.form.get('dropoff', '').strip()
        travel_date = request.form.get('travel_date', '').strip()
        travel_time = request.form.get('travel_time', '').strip()
        passengers = request.form.get('passengers', '1').strip() or '1'
        notes = request.form.get('notes', '').strip()

        if not customer_name or not pickup or not dropoff or not travel_date:
            flash('Please complete the booking form.', 'error')
        else:
            try:
                passengers_int = max(int(passengers), 1)
            except ValueError:
                passengers_int = 1
            booking = Booking(
                customer_name=customer_name,
                phone=phone,
                pickup=pickup,
                dropoff=dropoff,
                travel_date=travel_date,
                travel_time=travel_time,
                passengers=passengers_int,
                notes=notes,
                created_by=current_user() if current_user() and current_user().role == 'user' else None,
            )
            db.session.add(booking)
            db.session.commit()
            flash(f'Booking received. Reference {booking.reference}.', 'success')
            return redirect(url_for('book'))
    return render_template('book.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/board/login', methods=['GET', 'POST'])
def board_login():
    user = current_user()
    if user and user.role == 'admin':
        return redirect(url_for('board_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.role == 'admin' and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Admin access granted, {user.full_name}.', 'success')
            return redirect(url_for('board_dashboard'))
        flash('Admin login failed.', 'error')
    return render_template('board/login.html')


@app.route('/board')
@admin_required
def board_dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    active_announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('board/dashboard.html', users=users, recent_bookings=recent_bookings, active_announcements=active_announcements)


@app.route('/board/users', methods=['GET', 'POST'])
@admin_required
def board_users():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user').strip().lower()
        if not full_name or not email or len(password) < 6:
            flash('Provide a name, email, and password with at least 6 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('That email is already in use.', 'error')
        else:
            user = User(full_name=full_name, email=email, role=role if role in {'user', 'admin', 'driver'} else 'user')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('User added.', 'success')
            return redirect(url_for('board_users'))
    users = User.query.order_by(User.created_at.desc()).all()
    drivers = [u for u in users if u.role == 'driver']
    return render_template('board/users.html', users=users, drivers=drivers)


@app.route('/board/users/<int:user_id>/role', methods=['POST'])
@admin_required
def board_change_role(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('board_users'))
    new_role = request.form.get('role', 'user').strip().lower()
    user.role = new_role if new_role in {'user', 'admin', 'driver'} else 'user'
    db.session.commit()
    flash('Role updated.', 'success')
    return redirect(url_for('board_users'))


@app.route('/board/bookings', methods=['GET', 'POST'])
@admin_required
def board_bookings():
    if request.method == 'POST':
        booking_id = request.form.get('booking_id', type=int)
        booking = db.session.get(Booking, booking_id)
        if booking:
            booking.status = request.form.get('status', booking.status)
            driver_id = request.form.get('assigned_driver_id', type=int)
            booking.assigned_driver_id = driver_id or None
            db.session.commit()
            flash('Booking updated.', 'success')
        return redirect(url_for('board_bookings'))
    status = request.args.get('status', 'all')
    q = Booking.query.order_by(Booking.created_at.desc())
    if status != 'all':
        q = q.filter_by(status=status)
    bookings = q.all()
    drivers = User.query.filter_by(role='driver').order_by(User.full_name.asc()).all()
    return render_template('board/bookings.html', bookings=bookings, selected_status=status, drivers=drivers)


@app.route('/board/announcements', methods=['GET', 'POST'])
@admin_required
def board_announcements():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        audience = request.form.get('audience', 'All users').strip()
        if not title or not body:
            flash('Add a title and message.', 'error')
        else:
            db.session.add(Announcement(title=title, body=body, audience=audience))
            db.session.commit()
            flash('Announcement published.', 'success')
            return redirect(url_for('board_announcements'))
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('board/announcements.html', announcements=announcements)


@app.route('/board/announcements/<int:announcement_id>/toggle', methods=['POST'])
@admin_required
def board_toggle_announcement(announcement_id):
    item = db.session.get(Announcement, announcement_id)
    if item:
        item.active = not item.active
        db.session.commit()
        flash('Announcement status changed.', 'success')
    return redirect(url_for('board_announcements'))


@app.route('/drivers/login', methods=['GET', 'POST'])
def drivers_login():
    user = current_user()
    if user and user.role == 'driver':
        return redirect(url_for('drivers_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.role == 'driver' and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Welcome, {user.full_name}.', 'success')
            return redirect(url_for('drivers_dashboard'))
        flash('Driver login failed.', 'error')
    return render_template('drivers/login.html')


@app.route('/drivers')
@driver_required
def drivers_dashboard():
    driver = current_user()
    assigned = Booking.query.filter_by(assigned_driver_id=driver.id).order_by(Booking.created_at.desc()).all()
    pending = Booking.query.filter(Booking.assigned_driver_id.is_(None)).order_by(Booking.created_at.desc()).limit(5).all()
    return render_template('drivers/dashboard.html', assigned=assigned, pending=pending)


@app.route('/drivers/bookings/<int:booking_id>/status', methods=['POST'])
@driver_required
def driver_update_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    driver = current_user()
    if not booking or booking.assigned_driver_id != driver.id:
        flash('That booking is not assigned to you.', 'error')
        return redirect(url_for('drivers_dashboard'))
    new_status = request.form.get('status', booking.status)
    booking.status = new_status
    db.session.commit()
    flash('Booking status updated.', 'success')
    return redirect(url_for('drivers_dashboard'))


@app.route('/api/status')
def api_status():
    return jsonify({
        'ok': True,
        'name': 'City Connect',
        'users': User.query.count(),
        'bookings': Booking.query.count(),
        'time': datetime.utcnow().isoformat() + 'Z',
    })


@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')


@app.route('/sw.js')
def service_worker():
    return app.send_static_file('js/sw.js')


@app.errorhandler(404)
def not_found(_):
    return render_template('404.html'), 404



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )