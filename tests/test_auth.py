"""Tests for authentication and role-based access control."""
import pytest
import json
from app import create_app, db
from app.models import Recipe
from app.auth import User

# Valid test password that meets complexity requirements
TEST_PASSWORD = 'Password123'


# ============================================================================
# Helpers
# ============================================================================

def _register(client, username, password, role='viewer'):
    return client.post('/api/auth/register',
                       data=json.dumps({'username': username, 'password': password, 'role': role}),
                       content_type='application/json')


def _login(client, username, password):
    resp = client.post('/api/auth/login',
                       data=json.dumps({'username': username, 'password': password}),
                       content_type='application/json')
    data = json.loads(resp.data)
    return data.get('access_token'), data.get('user', {})


def _auth_header(token):
    return {'Authorization': f'Bearer {token}'} if token else {}


def _create_recipe(client, token, title='Test Recipe'):
    return client.post('/api/recipes',
                       data=json.dumps({
                           'title': title,
                           'instructions': '1. Do stuff.',
                           'tags': [{'name': 'test', 'tag_type': 'custom'}]
                       }),
                       content_type='application/json',
                       headers=_auth_header(token))


def _update_recipe(client, token, recipe_id, title='Updated'):
    return client.put(f'/api/recipes/{recipe_id}',
                      data=json.dumps({'title': title, 'instructions': '1. Updated.'}),
                      content_type='application/json',
                      headers=_auth_header(token))


def _delete_recipe(client, token, recipe_id):
    return client.delete(f'/api/recipes/{recipe_id}',
                         headers=_auth_header(token))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    app = create_app('development')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-exactly-32-bytes",
        "JWT_SECRET_KEY": "test-jwt-secret-key-exactly-32-bytes",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def bootstrap_admin(app):
    """Create an admin user and return login credentials."""
    with app.app_context():
        user = User(username='admin', role='admin')
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
    return {'username': 'admin', 'password': TEST_PASSWORD}


@pytest.fixture
def admin_token(client, bootstrap_admin):
    token, _ = _login(client, bootstrap_admin['username'], bootstrap_admin['password'])
    return token


@pytest.fixture
def editor_token(client, app, admin_token):
    """Create an editor user via admin, return token."""
    # Register as viewer first
    _register(client, 'editor_user', TEST_PASSWORD, role='viewer')
    # Admin upgrades to editor
    client.put('/api/auth/users/2/role',
               data=json.dumps({'role': 'editor'}),
               content_type='application/json',
               headers=_auth_header(admin_token))
    token, _ = _login(client, 'editor_user', TEST_PASSWORD)
    return token


@pytest.fixture
def viewer_token(client):
    _register(client, 'viewer_user', TEST_PASSWORD, role='viewer')
    token, _ = _login(client, 'viewer_user', TEST_PASSWORD)
    return token


# ============================================================================
# Registration Tests
# ============================================================================

class TestRegistration:
    def test_register_viewer(self, client):
        resp = _register(client, 'newuser', TEST_PASSWORD)
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['username'] == 'newuser'
        assert data['role'] == 'viewer'

    def test_register_first_user_as_admin(self, client):
        """First user in the system can register as admin."""
        resp = _register(client, 'firstadmin', TEST_PASSWORD, role='admin')
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['role'] == 'admin'

    def test_register_non_first_as_admin_denied(self, client, bootstrap_admin):
        """Only the first user can self-assign admin. Others need an admin."""
        resp = _register(client, 'wannabe_admin', TEST_PASSWORD, role='admin')
        assert resp.status_code == 403

    def test_register_duplicate_username(self, client):
        _register(client, 'sameuser', TEST_PASSWORD)
        resp = _register(client, 'sameuser', TEST_PASSWORD)
        assert resp.status_code == 409

    def test_register_short_password(self, client):
        resp = _register(client, 'user', 'short')
        assert resp.status_code == 400

    def test_register_short_username(self, client):
        resp = _register(client, 'ab', TEST_PASSWORD)
        assert resp.status_code == 400

    def test_register_invalid_role(self, client):
        resp = _register(client, 'user', TEST_PASSWORD, role='superuser')
        assert resp.status_code == 400

    def test_register_case_insensitive_duplicate(self, client):
        _register(client, 'CaseUser', TEST_PASSWORD)
        resp = _register(client, 'caseuser', TEST_PASSWORD)
        assert resp.status_code == 409


# ============================================================================
# Login Tests
# ============================================================================

class TestLogin:
    def test_login_success(self, client, bootstrap_admin):
        token, user = _login(client, bootstrap_admin['username'], bootstrap_admin['password'])
        assert token is not None
        assert user['role'] == 'admin'

    def test_login_wrong_password(self, client, bootstrap_admin):
        resp = client.post('/api/auth/login',
                          data=json.dumps({'username': bootstrap_admin['username'], 'password': 'wrong'}),
                          content_type='application/json')
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post('/api/auth/login',
                          data=json.dumps({'username': 'nobody', 'password': TEST_PASSWORD}),
                          content_type='application/json')
        assert resp.status_code == 401

    def test_login_case_insensitive(self, client, bootstrap_admin):
        token, _ = _login(client, bootstrap_admin['username'].upper(), bootstrap_admin['password'])
        assert token is not None

    def test_login_empty_fields(self, client):
        resp = client.post('/api/auth/login',
                          data=json.dumps({'username': '', 'password': ''}),
                          content_type='application/json')
        assert resp.status_code == 400


# ============================================================================
# GET /me Tests
# ============================================================================

class TestCurrentUser:
    def test_get_current_user(self, client, admin_token):
        resp = client.get('/api/auth/me', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['username'] == 'admin'

    def test_get_current_user_no_token(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401


# ============================================================================
# Role Management Tests
# ============================================================================

class TestRoleManagement:
    def test_admin_can_upgrade_viewer_to_editor(self, client, admin_token, viewer_token):
        # viewer is user 2 (1=admin from bootstrap_admin, 2=viewer_user from viewer_token fixture)
        resp = client.put('/api/auth/users/2/role',
                         data=json.dumps({'role': 'editor'}),
                         content_type='application/json',
                         headers=_auth_header(admin_token))
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['role'] == 'editor'

    def test_admin_cannot_demote_self(self, client, admin_token):
        resp = client.put('/api/auth/users/1/role',
                         data=json.dumps({'role': 'editor'}),
                         content_type='application/json',
                         headers=_auth_header(admin_token))
        assert resp.status_code == 400

    def test_non_admin_cannot_change_roles(self, client, viewer_token):
        resp = client.put('/api/auth/users/1/role',
                         data=json.dumps({'role': 'admin'}),
                         content_type='application/json',
                         headers=_auth_header(viewer_token))
        assert resp.status_code == 403

    def test_list_users_admin_only(self, client, admin_token, viewer_token):
        resp = client.get('/api/auth/users', headers=_auth_header(viewer_token))
        assert resp.status_code == 403

        resp = client.get('/api/auth/users', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert len(json.loads(resp.data)) >= 1


# ============================================================================
# Admin RBAC Tests (full CRUD)
# ============================================================================

class TestAdminAccess:
    def test_admin_can_create_recipe(self, client, admin_token):
        resp = _create_recipe(client, admin_token)
        assert resp.status_code == 201

    def test_admin_can_update_recipe(self, client, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _update_recipe(client, admin_token, recipe_id)
        assert resp.status_code == 200

    def test_admin_can_delete_recipe(self, client, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _delete_recipe(client, admin_token, recipe_id)
        assert resp.status_code == 204


# ============================================================================
# Editor RBAC Tests (CRU, no D)
# ============================================================================

class TestEditorAccess:
    def test_editor_can_create_recipe(self, client, editor_token):
        resp = _create_recipe(client, editor_token)
        assert resp.status_code == 201

    def test_editor_can_update_recipe(self, client, editor_token):
        recipe_id = json.loads(_create_recipe(client, editor_token).data)['id']
        resp = _update_recipe(client, editor_token, recipe_id)
        assert resp.status_code == 200

    def test_editor_cannot_delete_recipe(self, client, editor_token):
        recipe_id = json.loads(_create_recipe(client, editor_token).data)['id']
        resp = _delete_recipe(client, editor_token, recipe_id)
        assert resp.status_code == 403  # Forbidden, not 404


# ============================================================================
# Viewer RBAC Tests (read-only)
# ============================================================================

class TestViewerAccess:
    def test_viewer_can_list_recipes(self, client, viewer_token):
        resp = client.get('/api/recipes', headers=_auth_header(viewer_token))
        assert resp.status_code == 200

    def test_viewer_cannot_create_recipe(self, client, viewer_token):
        resp = _create_recipe(client, viewer_token)
        assert resp.status_code == 403  # Forbidden — has token but wrong role

    def test_viewer_cannot_update_recipe(self, client, viewer_token, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _update_recipe(client, viewer_token, recipe_id)
        assert resp.status_code == 403  # Forbidden — has token but wrong role

    def test_viewer_cannot_delete_recipe(self, client, viewer_token, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _delete_recipe(client, viewer_token, recipe_id)
        assert resp.status_code == 403  # Forbidden — has token but wrong role


# ============================================================================
# Unauthenticated Access Tests
# ============================================================================

class TestUnauthenticatedAccess:
    def test_unauthenticated_can_browse(self, client):
        resp = client.get('/api/recipes')
        assert resp.status_code == 200

    def test_unauthenticated_cannot_create(self, client):
        resp = _create_recipe(client, None)
        assert resp.status_code == 401

    def test_unauthenticated_cannot_update(self, client, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _update_recipe(client, None, recipe_id)
        assert resp.status_code == 401

    def test_unauthenticated_cannot_delete(self, client, admin_token):
        recipe_id = json.loads(_create_recipe(client, admin_token).data)['id']
        resp = _delete_recipe(client, None, recipe_id)
        assert resp.status_code == 401  # Unauthorized — no token at all
