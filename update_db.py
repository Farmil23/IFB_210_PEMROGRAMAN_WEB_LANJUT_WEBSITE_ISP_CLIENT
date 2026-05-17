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
        
    try:
        # Add voucher_duration_hours to package
        db.session.execute(text("ALTER TABLE package ADD COLUMN voucher_duration_hours INT NULL;"))
        print("Added package.voucher_duration_hours column.")
    except Exception as e:
        print(f"voucher_duration_hours column might already exist or error: {e}")

    try:
        db.session.execute(text("ALTER TABLE voucher ADD COLUMN expires_at DATETIME NULL;"))
        print("Added voucher.expires_at column.")
    except Exception as e:
        print(f"expires_at column might already exist or error: {e}")

    try:
        db.session.execute(text("ALTER TABLE transaction ADD COLUMN paid_at DATETIME NULL;"))
        print("Added transaction.paid_at column.")
    except Exception as e:
        print(f"paid_at column might already exist or error: {e}")

    try:
        db.session.execute(text("ALTER TABLE voucher ADD COLUMN valid_from DATETIME NULL;"))
        print("Added voucher.valid_from column.")
    except Exception as e:
        print(f"valid_from column might already exist or error: {e}")

    try:
        db.session.execute(text(
            "ALTER TABLE voucher ADD UNIQUE KEY uq_voucher_transaction_id (transaction_id)"
        ))
        print("Added unique voucher.transaction_id (satu transaksi satu voucher).")
    except Exception as e:
        print(f"uq_voucher_transaction_id might already exist, or duplicate rows: {e}")

    db.session.commit()
    print("Database updated successfully.")
