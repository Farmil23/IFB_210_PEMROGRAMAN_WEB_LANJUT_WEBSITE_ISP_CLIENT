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

    @app.context_processor
    def inject_presentation():

        from .timezone_util import WIB_LABEL

        return {
            'presentation_mode': not app.config.get('PRODUCTION', True),
            'wib_label': WIB_LABEL,
        }

    @app.template_filter('format_wib')
    def format_wib_filter(dt):

        from .timezone_util import format_wib

        return format_wib(dt)

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

        from .schema_migrate import ensure_schema

        ensure_schema()

        from .demo_reset import maybe_reset_demo_environment

        maybe_reset_demo_environment(app)

        # ==========================================
        # IMPORT ROUTES
        # ==========================================

        from . import routes

    return app