from . import db
from datetime import datetime

class User(db.Model): ## COLUMN USER
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    transactions = db.relationship('Transaction', backref='customer', lazy=True)

class Package(db.Model): ## COLUMN PACKAGE
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    package_type = db.Column(db.String(50), nullable=False) # 'bulanan' atau 'voucher_jam'
    price = db.Column(db.Float, nullable=False)
    speed = db.Column(db.String(50)) # contoh: '20 Mbps'

class Transaction(db.Model): ## COLUMN TRANSACTION
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, paid, failed
    stripe_session_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    voucher = db.relationship('Voucher', backref='transaction', uselist=False) # 1 to 1

class Voucher(db.Model): ## COLUMN VOUCHER
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='unused') # unused, active, expired