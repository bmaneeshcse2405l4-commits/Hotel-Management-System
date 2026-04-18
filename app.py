import os
from datetime import datetime, timezone, timedelta

import bcrypt
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_socketio import SocketIO, emit
from sqlalchemy import or_, and_, func

from models import db, User, Room, Booking, Invoice, FoodItem, FoodOrder, Review

# ----------------------------------------------------------------------
# Load local .env file (ignored in production where Render injects vars)
# ----------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)

# ------------------------------------------------------------------
# Config — all sensitive values come from environment variables
# ------------------------------------------------------------------
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-hotel-key-dev')

# Render provides postgres:// URLs; SQLAlchemy requires postgresql+psycopg://
# We use psycopg3 (psycopg[binary]) — must specify +psycopg dialect explicitly
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///hotel.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif _db_url.startswith('postgresql://'):
    _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session security — tighten in production
_is_production = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if _is_production:
    app.config['SESSION_COOKIE_SECURE'] = True

db.init_app(app)

# eventlet / threading mode needed for gunicorn on Render
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ------------------------------------------------------------------
# Bootstrap: create tables + seed default data
# ------------------------------------------------------------------
with app.app_context():
    try:
        db.create_all()

        # Default admin account
        if not User.query.filter_by(role='Admin').first():
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw('admin'.encode('utf-8'), salt)
            admin = User(name='Admin', email='admin@hotel.com',
                         password_hash=hashed.decode('utf-8'), role='Admin')
            db.session.add(admin)
            db.session.commit()

        # Seed menu if empty
        if not FoodItem.query.first():
            db.session.add_all([
                FoodItem(name='Club Sandwich',
                         description='Classic turkey and bacon club', price=15.0),
                FoodItem(name='Margherita Pizza',
                         description='Fresh mozzarella and basil', price=18.0),
                FoodItem(name='Caesar Salad',
                         description='Crispy romaine with parmesan', price=12.0),
            ])
            db.session.commit()
    except Exception as e:
        print(f'[STARTUP] DB init warning: {e}')

# ======================================================================
# PAGE ROUTES
# ======================================================================

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session)


@app.route('/login')
def login_page():
    return render_template('login.html')


# ======================================================================
# AUTH APIs
# ======================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Guest')

    if not name or not email or not password:
        return jsonify({'error': 'name, email and password are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    user = User(name=name, email=email,
                password_hash=hashed.decode('utf-8'), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Registered successfully'})


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if user and bcrypt.checkpw(data.get('password', '').encode('utf-8'),
                                user.password_hash.encode('utf-8')):
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name
        return jsonify({'message': 'Logged in', 'role': user.role})
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})


@app.route('/api/auth/me', methods=['GET'])
def me():
    """Return current session user details."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify({
        'user_id': session['user_id'],
        'name': session['name'],
        'role': session['role'],
    })


# ======================================================================
# ROOM APIs
# ======================================================================

@app.route('/api/rooms', methods=['GET', 'POST'])
def manage_rooms():
    if request.method == 'POST':
        if session.get('role') not in ['Admin', 'Receptionist']:
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.json
        room = Room(
            number=data['number'],
            type=data['type'],
            price=data['price'],
            status=data.get('status', 'Available')
        )
        db.session.add(room)
        db.session.commit()
        socketio.emit('room_update', {
            'action': 'add',
            'room': {'id': room.id, 'number': room.number, 'status': room.status}
        })
        return jsonify({'message': 'Room added'})

    rooms = Room.query.all()
    return jsonify([
        {'id': r.id, 'number': r.number, 'type': r.type,
         'price': r.price, 'status': r.status}
        for r in rooms
    ])


@app.route('/api/rooms/<int:room_id>', methods=['PUT', 'DELETE'])
def update_room(room_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    room = Room.query.get_or_404(room_id)

    if request.method == 'PUT':
        data = request.json
        if 'status' in data:
            room.status = data['status']
        if 'price' in data:
            room.price = data['price']
        if 'type' in data:
            room.type = data['type']
        db.session.commit()
        socketio.emit('room_update', {
            'action': 'update',
            'room': {'id': room.id, 'number': room.number, 'status': room.status}
        })
        return jsonify({'message': 'Room updated'})

    db.session.delete(room)
    db.session.commit()
    socketio.emit('room_update', {'action': 'delete', 'room_id': room_id})
    return jsonify({'message': 'Room deleted'})


# ======================================================================
# BOOKING APIs
# ======================================================================

@app.route('/api/bookings', methods=['GET', 'POST'])
def manage_bookings():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        room_id = data['room_id']

        # Prevent double booking
        overlapping = Booking.query.filter(
            Booking.room_id == room_id,
            Booking.status.in_(['Confirmed', 'Checked-In']),
            Booking.start_date < end_date,
            Booking.end_date > start_date
        ).first()
        if overlapping:
            return jsonify({'error': 'Room already booked for these dates'}), 400

        room = Room.query.get(room_id)
        if start_date.date() == datetime.now(timezone.utc).date():
            room.status = 'Booked'

        payment_type = data.get('payment_type', 'Card')
        booking = Booking(
            user_id=session['user_id'],
            room_id=room_id,
            start_date=start_date,
            end_date=end_date,
            payment_type=payment_type
        )
        db.session.add(booking)
        db.session.commit()

        socketio.emit('notification',
                      {'message': f'New booking for Room {room.number}'},
                      broadcast=True)
        socketio.emit('room_update', {
            'action': 'update',
            'room': {'id': room.id, 'number': room.number, 'status': room.status}
        })
        return jsonify({'message': 'Booking confirmed', 'booking_id': booking.id})

    # GET — staff sees all, guest sees their own
    if session.get('role') in ['Admin', 'Receptionist']:
        bookings = Booking.query.all()
    elif 'user_id' in session:
        bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    else:
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify([{
        'id': b.id,
        'room_id': b.room_id,
        'room_number': b.room.number,
        'user_id': b.user_id,
        'user_name': b.user.name,
        'start_date': b.start_date.isoformat(),
        'end_date': b.end_date.isoformat(),
        'status': b.status,
        'payment_type': b.payment_type,
        'created_at': b.created_at.isoformat(),
    } for b in bookings])


@app.route('/api/bookings/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    """Get a single booking's details."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    booking = Booking.query.get_or_404(booking_id)

    # Guests can only see their own bookings
    if session.get('role') not in ['Admin', 'Receptionist']:
        if booking.user_id != session['user_id']:
            return jsonify({'error': 'Forbidden'}), 403

    return jsonify({
        'id': booking.id,
        'room_id': booking.room_id,
        'room_number': booking.room.number,
        'room_type': booking.room.type,
        'room_price': booking.room.price,
        'user_id': booking.user_id,
        'user_name': booking.user.name,
        'start_date': booking.start_date.isoformat(),
        'end_date': booking.end_date.isoformat(),
        'status': booking.status,
        'payment_type': booking.payment_type,
        'created_at': booking.created_at.isoformat(),
    })


@app.route('/api/bookings/<int:booking_id>/cancel', methods=['PUT'])
def cancel_booking(booking_id):
    """Cancel a Confirmed booking. Guests can cancel their own; staff can cancel any."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    booking = Booking.query.get_or_404(booking_id)

    # Guests can only cancel their own bookings
    if session.get('role') not in ['Admin', 'Receptionist']:
        if booking.user_id != session['user_id']:
            return jsonify({'error': 'Forbidden'}), 403

    if booking.status != 'Confirmed':
        return jsonify({'error': 'Only Confirmed bookings can be cancelled'}), 400

    booking.status = 'Cancelled'
    # Free the room if it was marked Booked for today
    if booking.room.status == 'Booked':
        booking.room.status = 'Available'
    db.session.commit()

    socketio.emit('room_update', {
        'action': 'update',
        'room': {'id': booking.room.id, 'number': booking.room.number,
                 'status': booking.room.status}
    })
    socketio.emit('notification',
                  {'message': f'Booking for Room {booking.room.number} cancelled.'})
    return jsonify({'message': 'Booking cancelled successfully'})


@app.route('/api/user/bookings', methods=['GET'])
def get_user_bookings():
    """Return the logged-in guest's booking history."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    bookings = Booking.query.filter_by(user_id=session['user_id'])\
                            .order_by(Booking.created_at.desc()).all()
    return jsonify([{
        'id': b.id,
        'room_number': b.room.number,
        'room_type': b.room.type,
        'start_date': b.start_date.isoformat(),
        'end_date': b.end_date.isoformat(),
        'status': b.status,
        'payment_type': b.payment_type,
    } for b in bookings])


@app.route('/api/bookings/<int:booking_id>/checkin', methods=['POST'])
def checkin(booking_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    booking = Booking.query.get_or_404(booking_id)
    if booking.status != 'Confirmed':
        return jsonify({'error': 'Invalid state'}), 400

    booking.status = 'Checked-In'
    booking.room.status = 'Occupied'
    db.session.commit()

    socketio.emit('room_update', {
        'action': 'update',
        'room': {'id': booking.room.id, 'status': 'Occupied'}
    })
    socketio.emit('notification',
                  {'message': f'Room {booking.room.number} checked in.'})
    return jsonify({'message': 'Checked In'})


@app.route('/api/bookings/<int:booking_id>/checkout', methods=['POST'])
def checkout(booking_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    booking = Booking.query.get_or_404(booking_id)
    if booking.status != 'Checked-In':
        return jsonify({'error': 'Invalid state'}), 400

    days = (booking.end_date - booking.start_date).days or 1
    room_charges = float(days * booking.room.price)
    extra_charges = sum(o.total_price for o in booking.food_orders)
    taxes = (room_charges + extra_charges) * 0.1
    total = room_charges + extra_charges + taxes

    invoice = Invoice(
        booking_id=booking.id,
        room_charges=room_charges,
        extra_charges=extra_charges,
        total=total,
        payment_status='Paid'
    )
    db.session.add(invoice)

    booking.status = 'Checked-Out'
    booking.room.status = 'Available'
    db.session.commit()

    socketio.emit('room_update', {
        'action': 'update',
        'room': {'id': booking.room.id, 'status': 'Available'}
    })
    socketio.emit('notification', {
        'message': f'Room {booking.room.number} checked out. Bill: ₹{total:.2f}'
    })
    return jsonify({
        'message': 'Checked out successfully. Bill generated.',
        'invoice_id': invoice.id,
        'room_charges': room_charges,
        'extra_charges': extra_charges,
        'taxes': round(taxes, 2),
        'total': round(total, 2),
    })


# ======================================================================
# INVOICE APIs
# ======================================================================

@app.route('/api/user/invoices', methods=['GET'])
def get_user_invoices():
    """Return all invoices for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    invoices = Invoice.query.filter(
        Invoice.booking_id.in_([b.id for b in bookings])
    ).all()
    return jsonify([{
        'id': i.id,
        'booking_id': i.booking_id,
        'room': i.booking.room.number,
        'room_charges': i.room_charges,
        'extra_charges': i.extra_charges,
        'taxes': round(i.total - i.room_charges - i.extra_charges, 2),
        'total': i.total,
        'payment_status': i.payment_status,
        'date': i.booking.end_date.isoformat(),
        'created_at': i.created_at.isoformat(),
    } for i in invoices])


@app.route('/api/admin/invoices', methods=['GET'])
def get_all_invoices():
    """Admin — fetch all invoices with full detail."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    return jsonify([{
        'id': i.id,
        'booking_id': i.booking_id,
        'room': i.booking.room.number,
        'guest_name': i.booking.user.name,
        'guest_email': i.booking.user.email,
        'room_charges': i.room_charges,
        'extra_charges': i.extra_charges,
        'taxes': round(i.total - i.room_charges - i.extra_charges, 2),
        'total': i.total,
        'payment_status': i.payment_status,
        'check_in': i.booking.start_date.isoformat(),
        'check_out': i.booking.end_date.isoformat(),
        'created_at': i.created_at.isoformat(),
    } for i in invoices])


# ======================================================================
# ADMIN — STATS
# ======================================================================

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    total_rooms = Room.query.count()
    occupied = Room.query.filter_by(status='Occupied').count()
    available = Room.query.filter_by(status='Available').count()

    IST = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)

    today_start_ist = datetime.combine(
        now_ist.date(), datetime.min.time()).replace(tzinfo=IST)
    today_start = today_start_ist.astimezone(timezone.utc)

    week_start_ist = today_start_ist - timedelta(days=today_start_ist.weekday())
    week_start = week_start_ist.astimezone(timezone.utc)

    month_start_ist = datetime.combine(
        now_ist.date().replace(day=1), datetime.min.time()).replace(tzinfo=IST)
    month_start = month_start_ist.astimezone(timezone.utc)

    today_bookings = Booking.query.filter(
        Booking.created_at >= today_start).count()

    rev_today = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.payment_status == 'Paid',
        Invoice.created_at >= today_start).scalar() or 0
    rev_weekly = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.payment_status == 'Paid',
        Invoice.created_at >= week_start).scalar() or 0
    rev_monthly = db.session.query(func.sum(Invoice.total)).filter(
        Invoice.payment_status == 'Paid',
        Invoice.created_at >= month_start).scalar() or 0

    def get_live_food_rev(start_time):
        active_ids = [b.id for b in Booking.query.filter_by(
            status='Checked-In').all()]
        if not active_ids:
            return 0
        return db.session.query(func.sum(FoodOrder.total_price)).filter(
            FoodOrder.booking_id.in_(active_ids),
            FoodOrder.status == 'Delivered',
            FoodOrder.created_at >= start_time
        ).scalar() or 0

    rev_today += get_live_food_rev(today_start)
    rev_weekly += get_live_food_rev(week_start)
    rev_monthly += get_live_food_rev(month_start)

    return jsonify({
        'total_rooms': total_rooms,
        'occupied': occupied,
        'available': available,
        'today_bookings': today_bookings,
        'revenue_today': round(rev_today, 2),
        'revenue_weekly': round(rev_weekly, 2),
        'revenue_monthly': round(rev_monthly, 2),
    })


# ======================================================================
# ADMIN — USER / STAFF MANAGEMENT
# ======================================================================

@app.route('/api/admin/users', methods=['GET'])
def list_users():
    """Admin — list all registered users."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    users = User.query.order_by(User.id).all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role,
    } for u in users])


@app.route('/api/admin/staff', methods=['POST'])
def add_staff():
    """Admin — create a new staff (Receptionist / Housekeeper) account."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'Receptionist')

    if not name or not email or not password:
        return jsonify({'error': 'name, email and password are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    user = User(name=name, email=email,
                password_hash=hashed.decode('utf-8'), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': f'{role} account created successfully',
                    'user_id': user.id})


@app.route('/api/admin/staff/<int:user_id>', methods=['DELETE'])
def remove_staff(user_id):
    """Admin — remove a staff or guest account (cannot delete own account)."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete your own account'}), 400

    user = User.query.get_or_404(user_id)
    if user.role == 'Admin':
        return jsonify({'error': 'Cannot delete another Admin account'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {user.name} deleted successfully'})


# ======================================================================
# FOOD MENU APIs
# ======================================================================

@app.route('/api/food', methods=['GET'])
def get_food():
    """Public — list all available food items."""
    items = FoodItem.query.filter_by(is_available=True).all()
    return jsonify([{
        'id': i.id,
        'name': i.name,
        'description': i.description,
        'price': i.price,
        'image_url': i.image_url,
    } for i in items])


@app.route('/api/admin/food', methods=['POST'])
def add_food_item():
    """Admin — add a new food item to the menu."""
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    name = data.get('name')
    price = data.get('price')
    if not name or price is None:
        return jsonify({'error': 'name and price are required'}), 400

    item = FoodItem(
        name=name,
        description=data.get('description', ''),
        price=float(price),
        image_url=data.get('image_url'),
        is_available=data.get('is_available', True)
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'message': 'Food item added', 'item_id': item.id}), 201


@app.route('/api/admin/food/<int:item_id>', methods=['PUT'])
def update_food_item(item_id):
    """Admin — update an existing food item."""
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403

    item = FoodItem.query.get_or_404(item_id)
    data = request.json

    if 'name' in data:
        item.name = data['name']
    if 'description' in data:
        item.description = data['description']
    if 'price' in data:
        item.price = float(data['price'])
    if 'image_url' in data:
        item.image_url = data['image_url']
    if 'is_available' in data:
        item.is_available = bool(data['is_available'])

    db.session.commit()
    return jsonify({'message': 'Food item updated'})


@app.route('/api/admin/food/<int:item_id>', methods=['DELETE'])
def delete_food_item(item_id):
    """Admin — soft-delete (mark unavailable) or hard-delete a food item."""
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403

    item = FoodItem.query.get_or_404(item_id)
    hard_delete = request.args.get('hard', 'false').lower() == 'true'

    if hard_delete:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Food item permanently deleted'})
    else:
        item.is_available = False
        db.session.commit()
        return jsonify({'message': 'Food item hidden from menu'})


# ======================================================================
# FOOD ORDER APIs
# ======================================================================

@app.route('/api/food/order', methods=['POST'])
def order_food():
    """Guest — place a food/room-service order (must be Checked-In)."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    booking = Booking.query.filter_by(
        user_id=session['user_id'], status='Checked-In').first()
    if not booking:
        return jsonify({
            'error': 'No active room found. You must be Checked-In to order food.'
        }), 400

    data = request.json
    food_id = data.get('food_id')
    custom_request = data.get('custom_request')
    qty = int(data.get('quantity', 1))

    if food_id:
        food = FoodItem.query.get(food_id)
        if not food:
            return jsonify({'error': 'Food item not found'}), 404
        if not food.is_available:
            return jsonify({'error': 'Food item is currently unavailable'}), 400
        order = FoodOrder(
            booking_id=booking.id,
            food_item_id=food.id,
            quantity=qty,
            total_price=food.price * qty
        )
    elif custom_request:
        order = FoodOrder(
            booking_id=booking.id,
            custom_request=custom_request,
            quantity=qty,
            total_price=200.0 * qty  # default base price for custom orders
        )
    else:
        return jsonify({'error': 'Must provide food_id or custom_request'}), 400

    db.session.add(order)
    db.session.commit()

    socketio.emit('notification', {
        'message': f'New food order for Room {booking.room.number}'
    }, broadcast=True)
    return jsonify({'message': 'Food ordered successfully!', 'order_id': order.id})


@app.route('/api/admin/food_orders', methods=['GET'])
def get_food_orders():
    """Staff — list pending and accepted food orders."""
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403

    orders = FoodOrder.query.filter(
        FoodOrder.status.in_(['Pending', 'Accepted'])
    ).order_by(FoodOrder.created_at.asc()).all()

    return jsonify([{
        'id': o.id,
        'room': o.booking.room.number,
        'food': o.food_item.name if o.food_item else f'Custom: {o.custom_request}',
        'quantity': o.quantity,
        'total': o.total_price,
        'status': o.status,
        'image': o.food_item.image_url if o.food_item else '',
        'created_at': o.created_at.isoformat(),
    } for o in orders])


@app.route('/api/admin/food_orders/history', methods=['GET'])
def get_food_orders_history():
    """Staff — list delivered food orders (history)."""
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403

    limit = int(request.args.get('limit', 50))
    orders = FoodOrder.query.filter_by(status='Delivered')\
                            .order_by(FoodOrder.created_at.desc())\
                            .limit(limit).all()
    return jsonify([{
        'id': o.id,
        'room': o.booking.room.number,
        'food': o.food_item.name if o.food_item else f'Custom: {o.custom_request}',
        'quantity': o.quantity,
        'total': o.total_price,
        'status': o.status,
        'created_at': o.created_at.isoformat(),
    } for o in orders])


@app.route('/api/admin/food_orders/<int:order_id>/accept', methods=['POST'])
def accept_food(order_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    order = FoodOrder.query.get_or_404(order_id)
    if order.status != 'Pending':
        return jsonify({'error': 'Order must be Pending to accept'}), 400
    order.status = 'Accepted'
    db.session.commit()
    return jsonify({'message': 'Order Accepted & Preparing'})


@app.route('/api/admin/food_orders/<int:order_id>/deliver', methods=['POST'])
def deliver_food(order_id):
    if session.get('role') not in ['Admin', 'Receptionist']:
        return jsonify({'error': 'Unauthorized'}), 403
    order = FoodOrder.query.get_or_404(order_id)
    if order.status != 'Accepted':
        return jsonify({'error': 'Order must be Accepted before marking Delivered'}), 400
    order.status = 'Delivered'
    db.session.commit()
    socketio.emit('notification', {
        'message': f'Food delivered to Room {order.booking.room.number}'
    })
    return jsonify({'message': 'Order marked as Delivered'})


# ======================================================================
# REVIEW APIs
# ======================================================================

@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Logged-in user — submit a hotel review."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    rating = int(data.get('rating', 5))
    comment = data.get('comment', '').strip()

    if rating < 1 or rating > 5 or not comment:
        return jsonify({'error': 'Rating must be 1–5 and comment cannot be empty'}), 400

    review = Review(user_id=session['user_id'], rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    return jsonify({'message': 'Thank you for your review!', 'review_id': review.id})


@app.route('/api/public/reviews', methods=['GET'])
def get_public_reviews():
    """Public — show top-rated (4–5 star) reviews on landing page."""
    reviews = Review.query.filter(Review.rating >= 4)\
                          .order_by(Review.created_at.desc())\
                          .limit(6).all()
    return jsonify([{
        'id': r.id,
        'user_name': r.user.name,
        'rating': r.rating,
        'comment': r.comment,
        'date': r.created_at.strftime('%B %d, %Y'),
    } for r in reviews])


@app.route('/api/admin/reviews', methods=['GET'])
def get_all_reviews():
    """Admin — list all reviews for moderation."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'user_name': r.user.name,
        'user_email': r.user.email,
        'rating': r.rating,
        'comment': r.comment,
        'date': r.created_at.strftime('%B %d, %Y'),
    } for r in reviews])


@app.route('/api/admin/reviews/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    """Admin — delete an inappropriate or spam review."""
    if session.get('role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    return jsonify({'message': 'Review deleted'})


# ======================================================================
# SOCKET IO EVENTS
# ======================================================================

@socketio.on('connect')
def on_connect():
    print('Client connected')


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


# ======================================================================
# ENTRY POINT (local dev only — Gunicorn imports app directly)
# ======================================================================

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000,
                 allow_unsafe_werkzeug=True)
