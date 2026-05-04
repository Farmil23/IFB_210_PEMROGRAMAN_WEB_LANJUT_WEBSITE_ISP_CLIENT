from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Add router_location
        db.session.execute(text("ALTER TABLE transaction ADD COLUMN router_location VARCHAR(100) NULL;"))
        print("Added router_location column.")
    except Exception as e:
        print(f"router_location column might already exist or error: {e}")
        
    try:
        # Add address
        db.session.execute(text("ALTER TABLE transaction ADD COLUMN address TEXT NULL;"))
        print("Added address column.")
    except Exception as e:
        print(f"address column might already exist or error: {e}")
        
    try:
        # Add phone_number
        db.session.execute(text("ALTER TABLE transaction ADD COLUMN phone_number VARCHAR(20) NULL;"))
        print("Added phone_number column.")
    except Exception as e:
        print(f"phone_number column might already exist or error: {e}")

    db.session.commit()
    print("Database updated successfully.")
