from app import create_app, db
from app.models import User
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Add is_admin
        db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;"))
        print("Added is_admin column.")
    except Exception as e:
        print(f"is_admin column might already exist or error: {e}")
        
    try:
        # Set test@itenas.id as admin
        user = User.query.filter_by(email='test@itenas.id').first()
        if user:
            user.is_admin = True
            db.session.commit()
            print("Set test@itenas.id as admin.")
        else:
            print("User test@itenas.id not found.")
    except Exception as e:
        print(f"Error setting admin: {e}")

