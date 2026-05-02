from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy() ## MEMANGGIL DB

def create_app(config_class=Config): ## FILE CONFIG FIJADIIN CONFIG UNTUK FILE .ENV
    app = Flask(__name__)
    app.config.from_object(config_class) ## CONFIG DITERAPKAMN
    
    db.init_app(app) ## MENYAMBUNGKAN DB KE FLASK
    
    with app.app_context():
        from . import models
        
        db.create_all() ## MEMBUAT COLUMN DATABASE JIKA BELUM ADA
    
    return app