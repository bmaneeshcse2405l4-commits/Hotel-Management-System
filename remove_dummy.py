from app import app, db
from models import Invoice

with app.app_context():
    # Remove all invoices that were dummy tests (e.g. exactly 5000 or 10000 total)
    dummy_invoices = Invoice.query.filter(Invoice.total.in_([5000, 10000])).all()
    for inv in dummy_invoices:
        print(f"Deleting dummy invoice {inv.id} with total {inv.total}")
        db.session.delete(inv)
    
    db.session.commit()
    print("Dummy invoices removed.")
