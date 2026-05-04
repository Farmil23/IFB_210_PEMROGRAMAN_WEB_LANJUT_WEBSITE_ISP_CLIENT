from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy() # INFO = MEMANGGIL DB
login_manager = LoginManager() # INFO = MEMANGGIL LOGIN MANAGER

def create_app(config_class=Config): # INFO = FILE CONFIG FIJADIIN CONFIG UNTUK FILE .ENV
    app = Flask(__name__)
    app.config.from_object(config_class) # INFO = CONFIG DITERAPKAMN
    
    db.init_app(app) # INFO = MENYAMBUNGKAN DB KE FLASK
    
    login_manager.init_app(app)
    login_manager.login_view = 'login' # INFO = route login
    login_manager.login_message = "Silakan login terlebih dahulu untuk mengakses halaman ini."
    
    with app.app_context():
        from . import models
        
        @login_manager.user_loader
        def load_user(user_id):
            return models.User.query.get(int(user_id))
        
        db.create_all() # INFO = MEMBUAT COLUMN DATABASE JIKA BELUM ADA

        from . import routes
    return app