"""Authentication module for Kitchen Companion."""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from flask_bcrypt import Bcrypt
from app import db

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()


class User(db.Model):
    """User model for authentication and authorization.

    Attributes:
        id: Unique identifier
        username: Login name (unique, case-insensitive)
        password_hash: bcrypt hashed password
        role: Authorization level (admin, editor, viewer)
        created_at: Account creation timestamp
    """
    __tablename__ = 'users'

    VALID_ROLES = ['admin', 'editor', 'viewer']
    DEFAULT_ROLE = 'viewer'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=DEFAULT_ROLE, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Hash and store a password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verify a password against the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert user to dict (excludes password hash)."""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# ============================================================================
# Decorators
# ============================================================================

def role_required(*allowed_roles):
    """Decorator to restrict endpoints by role.
    
    Must be used AFTER @jwt_required() in the decorator stack.
    """
    def decorator(fn):
        from functools import wraps
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
    """Shortcut for admin-only endpoints (includes delete)."""
    return role_required('admin')(fn)


def editor_or_admin(fn):
    """Shortcut for write-access endpoints (editor + admin, no delete)."""
    return role_required('editor', 'admin')(fn)


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
    if not password or len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Check uniqueness
    if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
        return jsonify({'error': 'Username already taken'}), 409

    # Determine role — only existing admins (via token) can assign roles
    request_role = data.get('role', User.DEFAULT_ROLE)
    if request_role not in User.VALID_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400

    # If requesting non-viewer role, must be authenticated as admin
    if request_role != 'viewer':
        # Check for existing admin-created users; allow first-user to be admin
        if User.query.count() > 0:
            return jsonify({'error': 'Only admins can assign roles. Register as viewer first.'}), 403

    user = User(username=username, role=request_role)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.route('/login', methods=['POST'])
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
def update_user_role(user_id):
    """Update a user's role (admin only).
    
    Request Body (JSON):
        role: New role (admin, editor, viewer)
    """
    from functools import wraps

    @wraps(update_user_role)
    @jwt_required()
    def _update(user_id):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403

        data = request.get_json()
        if not data or 'role' not in data:
            return jsonify({'error': 'Role is required'}), 400

        new_role = data['role']
        if new_role not in User.VALID_ROLES:
            return jsonify({'error': f'Invalid role. Must be one of: {User.VALID_ROLES}'}), 400

        user = User.query.get(user_id)
        if user is None:
            return jsonify({'error': 'User not found'}), 404

        # Prevent admin from demoting themselves
        if user.id == int(get_jwt_identity()) and new_role != 'admin':
            return jsonify({'error': 'Cannot change your own role'}), 400

        user.role = new_role
        db.session.commit()

        return jsonify(user.to_dict()), 200

    return _update(user_id)
