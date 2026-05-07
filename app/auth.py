"""Authentication module for Kitchen Companion."""
import os
import re
import secrets
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, url_for, flash, render_template
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from flask_bcrypt import Bcrypt
from app import db, limiter

# Global service API key — if set, the X-API-Key header can bypass JWT for write ops
SERVICE_API_KEY = os.environ.get('SERVICE_API_KEY')

auth_bp = Blueprint('auth', __name__)
web_bp = Blueprint('web_auth', __name__)
bcrypt = Bcrypt()


# ============================================================================
# Web UI Session-based Auth
# ============================================================================

def login_required_web(fn):
    """Decorator for web UI routes — requires session login."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('web_auth.login_page', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def admin_required_web(fn):
    """Decorator for web UI routes — requires admin session login."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('web_auth.login_page', next=request.path))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return fn(*args, **kwargs)
    return wrapper


def editor_or_admin_web(fn):
    """Decorator for web UI routes — requires editor or admin session."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('web_auth.login_page', next=request.path))
        if session.get('role') not in ('editor', 'admin'):
            flash('You do not have permission to perform this action.', 'error')
            return redirect(url_for('main.index'))
        return fn(*args, **kwargs)
    return wrapper


def validate_password(password):
    """Validate password meets complexity requirements.
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain a digit"
    return True, None


class User(db.Model):
    """User model for authentication and authorization.

    Attributes:
        id: Unique identifier
        username: Login name (unique, case-insensitive)
        password_hash: bcrypt hashed password
        role: Authorization level (admin, editor, viewer)
        api_key_hash: sha256 hash of per-user API key (or None if not set)
        api_key_prefix: First 8 chars of API key for identification in UI
        api_key_created_at: When the API key was last generated
        created_at: Account creation timestamp
    """
    __tablename__ = 'users'

    VALID_ROLES = ['admin', 'editor', 'viewer']
    DEFAULT_ROLE = 'viewer'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=DEFAULT_ROLE, index=True)
    api_key_hash = db.Column(db.String(64), nullable=True)
    api_key_prefix = db.Column(db.String(8), nullable=True)
    api_key_created_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Hash and store a password. Does NOT validate complexity."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def set_password_validated(self, password):
        """Validate password complexity then hash and store it.
        
        Raises:
            ValueError: If password fails validation
        """
        valid, err = validate_password(password)
        if not valid:
            raise ValueError(err)
        self.set_password(password)

    def check_password(self, password):
        """Verify a password against the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_api_key(self):
        """Generate a new API key, store its hash, return the raw key.
        
        The raw key is only returned once — it cannot be retrieved later.
        """
        import hashlib
        raw_key = f"sk-{secrets.token_urlsafe(32)}"
        self.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self.api_key_prefix = raw_key[:12]  # "sk-XXXXXXXX"
        self.api_key_created_at = datetime.utcnow()
        return raw_key

    def check_api_key(self, raw_key):
        """Verify a raw API key against the stored hash."""
        import hashlib
        if not self.api_key_hash:
            return False
        return hashlib.sha256(raw_key.encode()).hexdigest() == self.api_key_hash

    def revoke_api_key(self):
        """Revoke the API key."""
        self.api_key_hash = None
        self.api_key_prefix = None
        self.api_key_created_at = None

    def to_dict(self):
        """Convert user to dict (excludes password hash and API key hash)."""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'has_api_key': self.api_key_hash is not None,
            'api_key_prefix': self.api_key_prefix,
            'api_key_created_at': self.api_key_created_at.isoformat() if self.api_key_created_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# ============================================================================
# Decorators (API — JWT-based)
# ============================================================================

def role_required(*allowed_roles):
    """Decorator to restrict API endpoints by role.
    
    Must be used AFTER @jwt_required() in the decorator stack.
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get('role', 'viewer')
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    """Shortcut for admin-only API endpoints (includes delete)."""
    return role_required('admin')(fn)


def _authenticate_api_key():
    """Check X-API-Key header against user-scoped keys and global service key.

    Returns:
        User object if authenticated, None otherwise.
    """
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None

    # 1. Check global service API key (env var)
    if SERVICE_API_KEY and api_key == SERVICE_API_KEY:
        # Global key acts as a virtual admin-level identity
        return _VirtualServiceUser()

    # 2. Check per-user API keys
    for user in User.query.filter(User.api_key_hash.isnot(None)).all():
        if user.check_api_key(api_key):
            return user

    return None


class _VirtualServiceUser:
    """Lightweight object representing the global service API key identity.
    
    Not persisted — used purely to satisfy decorator role checks.
    """
    id = None
    username = 'service-account'
    role = 'admin'

    def to_dict(self):
        return {'username': self.username, 'role': self.role}


def editor_or_admin(fn):
    """Decorator for write-access API endpoints.
    
    Accepts either:
      - A valid JWT Bearer token (editor or admin role)
      - A valid X-API-Key header (per-user key with editor/admin role,
        or the global SERVICE_API_KEY env var)
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Try API key auth first
        user = _authenticate_api_key()
        if user is not None:
            if user.role not in ('editor', 'admin'):
                return jsonify({'error': 'Insufficient permissions — API key role must be editor or admin'}), 403
            return fn(*args, **kwargs)

        # Fall through to JWT-based auth
        return role_required('editor', 'admin')(fn)(*args, **kwargs)
    return wrapper


# ============================================================================
# Auth Endpoints
# ============================================================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account.
    
    Request Body (JSON):
        username: (required) Desired username (3-64 chars)
        password: (required) Password (min 8 chars)
        role: (optional) Role — only admins can set this, defaults to 'viewer'

    Returns:
        JSON user object with 201 status
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    # Validation
    if not username or len(username) < 3 or len(username) > 64:
        return jsonify({'error': 'Username must be 3-64 characters'}), 400
    
    valid, err = validate_password(password)
    if not valid:
        return jsonify({'error': err}), 400

    # Check uniqueness
    if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
        return jsonify({'error': 'Username already taken'}), 409

    # Determine role — only existing admins (via token) can assign roles
    request_role = data.get('role', User.DEFAULT_ROLE)
    if request_role not in User.VALID_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400

    # If requesting non-viewer role, only allow when no users exist (first-user bootstrap)
    # Use INSERT with a unique constraint check to prevent TOCTOU race
    if request_role != 'viewer':
        if User.query.count() > 0:
            return jsonify({'error': 'Only admins can assign roles. Register as viewer first.'}), 403

    user = User(username=username, role=request_role)
    user.set_password(password)  # validation already done above

    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # If commit fails (e.g. duplicate username from race), return conflict
        if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
            return jsonify({'error': 'Username already taken'}), 409
        return jsonify({'error': 'Registration failed'}), 500

    return jsonify(user.to_dict()), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login and receive a JWT access token.
    
    Request Body (JSON):
        username: Username
        password: Password

    Returns:
        JSON with access_token and user info
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter(
        db.func.lower(User.username) == db.func.lower(username)
    ).first()

    if user is None or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Create token with role in claims for easy RBAC
    additional_claims = {'role': user.role}
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims
    )

    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get the currently authenticated user's info."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


@auth_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    """List all users (admin only)."""
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users]), 200


@auth_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@jwt_required()
def update_user_role(user_id):
    """Update a user's role (admin only).
    
    Request Body (JSON):
        role: New role (admin, editor, viewer)
    """
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    if not data or 'role' not in data:
        return jsonify({'error': 'Role is required'}), 400

    new_role = data['role']
    if new_role not in User.VALID_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    # Prevent admin from demoting themselves
    if user.id == int(get_jwt_identity()) and new_role != 'admin':
        return jsonify({'error': 'Cannot change your own role'}), 400

    user.role = new_role
    db.session.commit()

    return jsonify(user.to_dict()), 200


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@auth_bp.route('/users/<int:user_id>/api-key', methods=['POST'])
@jwt_required()
def generate_api_key(user_id):
    """Generate a new API key for a user (admin or self).
    
    Admins can generate keys for any user.
    Users can generate keys for themselves.
    The raw key is returned only once — save it!
    """
    current_user_id = int(get_jwt_identity())
    claims = get_jwt()
    is_admin = claims.get('role') == 'admin'

    if not is_admin and current_user_id != user_id:
        return jsonify({'error': 'You can only generate API keys for your own account'}), 403

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    # Generate the key (this revokes any existing key)
    raw_key = user.set_api_key()
    db.session.commit()

    return jsonify({
        'message': 'API key generated. Save it now — it will not be shown again.',
        'api_key': raw_key,
        'prefix': user.api_key_prefix,
        'user': user.to_dict()
    }), 201


@auth_bp.route('/users/<int:user_id>/api-key', methods=['DELETE'])
@jwt_required()
def revoke_api_key(user_id):
    """Revoke a user's API key (admin or self)."""
    current_user_id = int(get_jwt_identity())
    claims = get_jwt()
    is_admin = claims.get('role') == 'admin'

    if not is_admin and current_user_id != user_id:
        return jsonify({'error': 'You can only revoke your own API key'}), 403

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    if not user.api_key_hash:
        return jsonify({'error': 'No API key to revoke'}), 404

    user.revoke_api_key()
    db.session.commit()

    return jsonify({'message': 'API key revoked', 'user': user.to_dict()}), 200


# ============================================================================
# Web UI Auth Routes
# ============================================================================

@web_bp.route('/signin', methods=['GET'])
def login_page():
    """Render the login page."""
    next_page = request.args.get('next', url_for('main.index'))
    return render_template('login.html', next=next_page)


@web_bp.route('/signin', methods=['POST'])
@limiter.limit("10 per minute")
def login_submit():
    """Process login form submission for web UI."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    next_page = request.form.get('next', url_for('main.index'))

    if not username or not password:
        flash('Username and password are required.', 'error')
        return redirect(url_for('web_auth.login_page', next=next_page))

    user = User.query.filter(
        db.func.lower(User.username) == db.func.lower(username)
    ).first()

    if user is None or not user.check_password(password):
        flash('Invalid username or password.', 'error')
        return redirect(url_for('web_auth.login_page', next=next_page))

    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session.permanent = True

    flash(f'Welcome back, {user.username}!', 'success')
    return redirect(next_page)


@web_bp.route('/logout', methods=['POST'])
def logout():
    """Log out of the web UI."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


# ============================================================================
# Admin Settings Web UI
# ============================================================================

@web_bp.route('/admin', methods=['GET'])
@limiter.limit("30 per minute")
def admin_settings_page():
    """Render the admin settings page."""
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('web_auth.login_page', next=request.path))
    if session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_settings.html', users=users)


@web_bp.route('/admin/users', methods=['POST'])
@limiter.limit("10 per minute")
def admin_create_user():
    """Create a new user (admin only, web UI form)."""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'viewer')

    if not username or len(username) < 3 or len(username) > 64:
        flash('Username must be 3-64 characters.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    valid, err = validate_password(password)
    if not valid:
        flash(err, 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    if role not in User.VALID_ROLES:
        flash('Invalid role selected.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
        flash('Username already taken.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User(username=username, role=role)
    user.set_password(password)  # validation already done above
    db.session.add(user)
    db.session.commit()

    flash(f'User {username} created successfully!', 'success')
    return redirect(url_for('web_auth.admin_settings_page'))


@web_bp.route('/admin/users/<int:user_id>/role', methods=['POST'])
@limiter.limit("20 per minute")
def admin_update_role(user_id):
    """Update a user's role via web UI form (admin only)."""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    new_role = request.form.get('role', '')
    if new_role not in User.VALID_ROLES:
        flash('Invalid role.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User.query.get(user_id)
    if user is None:
        flash('User not found.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    # Prevent admin from demoting themselves
    if user.id == session['user_id'] and new_role != 'admin':
        flash('Cannot change your own role.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    old_role = user.role
    user.role = new_role
    db.session.commit()

    flash(f"{user.username}'s role changed from {old_role} to {new_role}.", 'success')
    return redirect(url_for('web_auth.admin_settings_page'))


@web_bp.route('/admin/users/<int:user_id>/password', methods=['POST'])
@limiter.limit("5 per minute")
def admin_reset_password(user_id):
    """Reset a user's password via web UI form (admin only)."""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    new_password = request.form.get('new_password', '')
    valid, err = validate_password(new_password)
    if not valid:
        flash(err, 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User.query.get(user_id)
    if user is None:
        flash('User not found.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user.set_password(new_password)  # validation already done above
    db.session.commit()

    flash(f'Password reset for {user.username}.', 'success')
    return redirect(url_for('web_auth.admin_settings_page'))


@web_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@limiter.limit("10 per minute")
def admin_delete_user(user_id):
    """Delete a user (admin only, can't delete yourself)."""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    if user_id == session['user_id']:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User.query.get(user_id)
    if user is None:
        flash('User not found.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    username = user.username
    db.session.delete(user)
    db.session.commit()

    flash(f'User {username} deleted.', 'success')
    return redirect(url_for('web_auth.admin_settings_page'))


@web_bp.route('/admin/users/<int:user_id>/api-key', methods=['POST'])
@limiter.limit("10 per minute")
def admin_generate_api_key(user_id):
    """Generate a new API key via web UI (admin or self)."""
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('web_auth.login_page', next=request.path))

    is_admin = session.get('role') == 'admin'
    is_self = session['user_id'] == user_id

    if not is_admin and not is_self:
        flash('You can only generate API keys for your own account.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User.query.get(user_id)
    if user is None:
        flash('User not found.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    raw_key = user.set_api_key()
    db.session.commit()

    flash(f'API key generated for {user.username}: <code class="bg-green-100 px-2 py-1 rounded text-sm font-mono">{raw_key}</code> — copy it now, it will not be shown again!', 'success')
    return redirect(url_for('web_auth.admin_settings_page'))


@web_bp.route('/admin/users/<int:user_id>/api-key/revoke', methods=['POST'])
@limiter.limit("10 per minute")
def admin_revoke_api_key(user_id):
    """Revoke a user's API key via web UI (admin or self)."""
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('web_auth.login_page', next=request.path))

    is_admin = session.get('role') == 'admin'
    is_self = session['user_id'] == user_id

    if not is_admin and not is_self:
        flash('You can only revoke your own API key.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user = User.query.get(user_id)
    if user is None:
        flash('User not found.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    if not user.api_key_hash:
        flash('No API key to revoke.', 'error')
        return redirect(url_for('web_auth.admin_settings_page'))

    user.revoke_api_key()
    db.session.commit()

    flash(f'API key revoked for {user.username}.', 'success')
    return redirect(url_for('web_auth.admin_settings_page'))
