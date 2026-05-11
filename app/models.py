from . import db
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, db.Model): # INFO = COLUMN USER
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    transactions = db.relationship('Transaction', backref='customer', lazy=True)

class Package(db.Model): # INFO = COLUMN PACKAGE
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    package_type = db.Column(db.String(50), nullable=False) # INFO = 'bulanan' atau 'voucher_jam'
    price = db.Column(db.Float, nullable=False)
    speed = db.Column(db.String(50)) # INFO = contoh: '20 Mbps'
    
    # INFO = Tambahkan baris ini agar Transaction bisa memanggil .package
    transactions = db.relationship('Transaction', backref='package', lazy=True)

class Transaction(db.Model): # INFO = COLUMN TRANSACTION
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # INFO = pending, paid, failed
    stripe_session_id = db.Column(db.String(255), unique=True, nullable=True)
    router_location = db.Column(db.String(100), nullable=True) # INFO = Untuk voucher
    address = db.Column(db.Text, nullable=True) # INFO = Untuk langganan
    phone_number = db.Column(db.String(20), nullable=True) # INFO = Untuk langganan
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    voucher = db.relationship('Voucher', backref='transaction', uselist=False) # INFO = 1 to 1

class Voucher(db.Model): # INFO = COLUMN VOUCHER
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='unused') # INFO = unused, active, expired
    
    