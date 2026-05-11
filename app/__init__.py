from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from config import Config


# ==========================================
# INIT EXTENSIONS
# ==========================================

db = SQLAlchemy()

login_manager = LoginManager()


# ==========================================
# CREATE APP
# ==========================================

def create_app(config_class=Config):

    app = Flask(__name__)

    # ==========================================
    # LOAD CONFIG
    # ==========================================

    app.config.from_object(config_class)

    # ==========================================
    # SECRET KEY
    # ==========================================

    app.config['SECRET_KEY'] = 'btn-net-secret-key'

    # ==========================================
    # INIT DATABASE
    # ==========================================

    db.init_app(app)

    # ==========================================
    # INIT LOGIN MANAGER
    # ==========================================

    login_manager.init_app(app)

    login_manager.login_view = 'login'

    login_manager.login_message = (
        "Silakan login terlebih dahulu."
    )

    login_manager.login_message_category = "warning"

    # ==========================================
    # APP CONTEXT
    # ==========================================

    with app.app_context():

        # IMPORT MODELS
        from . import models

        # ==========================================
        # USER LOADER
        # ==========================================

        @login_manager.user_loader
        def load_user(user_id):

            return models.User.query.get(
                int(user_id)
            )

        # ==========================================
        # CREATE DATABASE TABLES
        # ==========================================

        db.create_all()

        # ==========================================
        # IMPORT ROUTES
        # ==========================================

        from . import routes

    return app