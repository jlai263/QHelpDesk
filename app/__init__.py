from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
mail = Mail()
bootstrap = Bootstrap()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Debug print for mail configuration
    print("Mail Configuration:")
    print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"MAIL_USE_SSL: {app.config.get('MAIL_USE_SSL')}")
    print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"Raw MAIL_PASSWORD length: {len(str(app.config.get('MAIL_PASSWORD')))}")
    print(f"MAIL_PASSWORD: {app.config.get('MAIL_PASSWORD')}")  # Be careful with this in production
    print(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    
    # Initialize CSRF protection but don't exempt routes yet
    csrf.init_app(app)

    # Register blueprints
    from app.auth import bp as auth_bp
    from app.admin import bp as admin_bp
    from app.main import bp as main_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(main_bp)

    # Now that blueprints are registered, exempt webhook routes from CSRF protection
    with app.app_context():
        if 'stripe_webhook' in main_bp.view_functions:
            csrf.exempt(main_bp.view_functions['stripe_webhook'])
        if 'webhook' in admin_bp.view_functions:
            csrf.exempt(admin_bp.view_functions['webhook'])

    return app

from app import models 