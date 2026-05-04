"""Kitchen Companion Flask Application Factory."""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name='default'):
    """Application factory pattern.
    
    Args:
        config_name: Configuration name ('development', 'production', 'default')
    
    Returns:
        Configured Flask application instance
    """
    from config import config_by_name
    
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    
    # Ensure upload directory exists
    upload_dir = os.path.join(app.static_folder, 'uploads', 'recipes')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    
    # Register blueprints
    from app.routes import api_bp, main_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Create database tables if they don't exist (safe for first run)
    # In production with migrations, this is a no-op if tables already exist
    with app.app_context():
        db.create_all()
    
    return app