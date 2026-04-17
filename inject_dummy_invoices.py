from app import app, db
from models import Invoice, Booking, Room
from datetime import datetime, timezone, timedelta

with app.app_context():
    # Find a valid booking to attach to, or fallback to 1 if testing
    b = Booking.query.first()
    if not b:
        print("No bookings found to attach invoices to!")
        exit()

    today = datetime.now(timezone.utc)
    
    # Invoice 1: Yesterday (April 1st) - Adds to Weekly and Monthly
    inv1 = Invoice(
        booking_id=b.id,
        room_charges=5000,
        extra_charges=0,
        total=5000,
        payment_status='Paid',
        created_at=today - timedelta(days=1)
    )
    
    # Invoice 2: Tuesday (March 31) - Adds to Weekly, NOT Monthly
    inv2 = Invoice(
        booking_id=b.id,
        room_charges=10000,
        extra_charges=0,
        total=10000,
        payment_status='Paid',
        created_at=today - timedelta(days=2)
    )

    db.session.add_all([inv1, inv2])
    db.session.commit()
    print("Successfully injected dummy invoices into the database!")
