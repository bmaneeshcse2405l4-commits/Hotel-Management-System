from app import app, db
from models import Review

with app.app_context():
    # Only creates tables that don't exist yet! Safe!
    db.create_all()
    print("Database synced successfully! Existing tables untouched. New tables created.")
