from app import app, db
from sqlalchemy import text

with app.app_context():
    # Attempt to alter table, safely passing if it already exists
    try:
        db.session.execute(text("ALTER TABLE invoice ADD COLUMN created_at DATETIME;"))
        db.session.commit()
        print("Column added successfully!")
    except Exception as e:
        db.session.rollback()
        print("Could not alter table. It might already exist or the DB is SQLite.")
        print(e)
        
    # If SQLite, the syntax is slightly different but basically similar
    # In SQLite, default constraint handles existing rows nicely.
    try:
        db.session.execute(text("UPDATE invoice SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;"))
        db.session.commit()
    except Exception as e:
        print(e)
