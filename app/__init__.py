"""Kitchen Companion Flask Application Factory."""
import os
import uuid
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)
jwt = JWTManager()
csrf = CSRFProtect()


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
    
    # Disable CSRF in testing mode
    if app.config.get('TESTING'):
        app.config['WTF_CSRF_ENABLED'] = False
    
    # Ensure upload directory exists
    upload_dir = os.path.join(app.static_folder, 'uploads', 'recipes')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)
    
    # Import blueprints
    from app.routes import api_bp, main_bp
    from app.auth import auth_bp, web_bp, bcrypt
    
    # API routes use JWT Bearer tokens, exempt from CSRF
    csrf.exempt(api_bp)
    csrf.exempt(auth_bp)
    
    # Initialize bcrypt
    bcrypt.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(web_bp, url_prefix='/api/auth')
    
    # ── Centralized error handlers ──────────────────────────────────
    
    def _error_ref():
        return str(uuid.uuid4())
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Consistent JSON error responses for all HTTP exceptions.
        
        API routes (prefix /api/) get JSON; web routes get HTML templates.
        """
        if request.path.startswith('/api/'):
            ref = _error_ref()
            response = jsonify({
                'error': e.description,
                'status': e.code,
                'ref': ref
            })
            response.status_code = e.code
            return response
        # Web UI routes get a friendly error page
        return render_template('error.html', code=e.code, message=e.description), e.code
    
    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found', 'status': 404}), 404
        return render_template('error.html', code=404, message='Page not found'), 404
    
    @app.errorhandler(500)
    def handle_internal_error(e):
        ref = _error_ref()
        app.logger.error(f'Internal server error (ref: {ref}): {e}')
        if request.path.startswith('/api/'):
            return jsonify({
                'error': f'Internal Server Error (ref: {ref})',
                'status': 500
            }), 500
        return render_template('error.html', code=500, message='Something went wrong'), 500
    
    return app
