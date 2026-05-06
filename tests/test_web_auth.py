"""Tests for web UI authentication (web_auth blueprint) and admin settings."""
import pytest
from app.auth import User
from app import db

TEST_PASSWORD = 'Test1234!'


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def web_admin_user(app):
    """Create an admin user for web auth tests."""
    with app.app_context():
        user = User(username='webadmin', role='admin')
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        return {'username': 'webadmin', 'password': TEST_PASSWORD, 'id': user.id}


@pytest.fixture
def web_editor_user(app):
    """Create an editor user for web auth tests."""
    with app.app_context():
        user = User(username='webeditor', role='editor')
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        return {'username': 'webeditor', 'password': TEST_PASSWORD, 'id': user.id}


@pytest.fixture
def web_viewer_user(app):
    """Create a viewer user for web auth tests."""
    with app.app_context():
        user = User(username='webviewer', role='viewer')
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        return {'username': 'webviewer', 'password': TEST_PASSWORD, 'id': user.id}


def _login_web(client, username, password):
    """Helper: log in via web UI form and return the response."""
    return client.post('/api/auth/signin', data={
        'username': username,
        'password': password,
        'next': '/'
    }, follow_redirects=True)


def _logout_web(client):
    """Helper: log out via web UI form."""
    return client.post('/api/auth/logout', follow_redirects=True)


# ============================================================================
# Login Page Tests
# ============================================================================

class TestLoginPage:
    def test_login_page_renders(self, client):
        """GET /api/auth/signin renders the login form."""
        resp = client.get('/api/auth/signin')
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_login_page_passes_next_param(self, client):
        """Login page includes next param in the form."""
        resp = client.get('/api/auth/signin?next=/recipes')
        assert resp.status_code == 200
        assert b'/recipes' in resp.data


# ============================================================================
# Web Login (Session) Tests
# ============================================================================

class TestWebLogin:
    def test_web_login_success(self, client, web_admin_user):
        """Successful web login sets session and redirects."""
        resp = _login_web(client, web_admin_user['username'], web_admin_user['password'])
        assert resp.status_code == 200
        # Should contain welcome flash message
        assert b'Welcome back' in resp.data or b'webadmin' in resp.data

    def test_web_login_wrong_password(self, client, web_admin_user):
        """Wrong password shows error on login page."""
        resp = client.post('/api/auth/signin', data={
            'username': web_admin_user['username'],
            'password': 'WrongPassword1'
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should be back on login page with error
        assert b'Invalid username or password' in resp.data

    def test_web_login_nonexistent_user(self, client):
        """Nonexistent user shows error."""
        resp = client.post('/api/auth/signin', data={
            'username': 'nosuchuser',
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid username or password' in resp.data

    def test_web_login_empty_fields(self, client):
        """Empty credentials show error."""
        resp = client.post('/api/auth/signin', data={
            'username': '',
            'password': ''
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Username and password are required' in resp.data

    def test_web_login_case_insensitive(self, client, web_admin_user):
        """Login is case-insensitive for username."""
        resp = _login_web(client, web_admin_user['username'].upper(), web_admin_user['password'])
        assert resp.status_code == 200
        assert b'Welcome back' in resp.data or b'webadmin' in resp.data

    def test_web_login_redirects_to_next(self, client, web_admin_user):
        """After login, user is redirected to the 'next' page."""
        resp = client.post('/api/auth/signin', data={
            'username': web_admin_user['username'],
            'password': web_admin_user['password'],
            'next': '/shopping-list'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Shopping List' in resp.data


# ============================================================================
# Web Logout Tests
# ============================================================================

class TestWebLogout:
    def test_logout_clears_session(self, client, web_admin_user):
        """Logout clears the session and redirects home."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = _logout_web(client)
        assert resp.status_code == 200
        # After logout, accessing /recipes/new should redirect to login
        resp2 = client.get('/recipes/new', follow_redirects=True)
        assert b'login' in resp2.data.lower()

    def test_logout_without_session(self, client):
        """Logout without session still works (no crash)."""
        resp = _logout_web(client)
        assert resp.status_code == 200


# ============================================================================
# Admin Settings Page Tests
# ============================================================================

class TestAdminSettingsPage:
    def test_admin_can_access_settings(self, client, web_admin_user):
        """Admin user can access the admin settings page."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.get('/api/auth/admin')
        assert resp.status_code == 200
        assert b'admin' in resp.data.lower() or b'Settings' in resp.data

    def test_unauthenticated_redirected_from_admin(self, client):
        """Unauthenticated users are redirected to login."""
        resp = client.get('/api/auth/admin', follow_redirects=True)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_editor_cannot_access_admin_settings(self, client, web_editor_user):
        """Editor is redirected from admin settings."""
        _login_web(client, web_editor_user['username'], web_editor_user['password'])
        resp = client.get('/api/auth/admin', follow_redirects=False)
        # Should be redirected (302) to index
        assert resp.status_code == 302
        assert resp.location == '/' or '/api/auth/signin' in resp.location

    def test_viewer_cannot_access_admin_settings(self, client, web_viewer_user):
        """Viewer is redirected from admin settings."""
        _login_web(client, web_viewer_user['username'], web_viewer_user['password'])
        resp = client.get('/api/auth/admin', follow_redirects=False)
        # Should be redirected to index
        assert resp.status_code == 302
        assert resp.location == '/' or '/api/auth/signin' in resp.location


# ============================================================================
# Admin Create User (Web UI) Tests
# ============================================================================

class TestAdminCreateUser:
    def test_admin_can_create_user(self, client, web_admin_user):
        """Admin can create a new user via web form."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post('/api/auth/admin/users', data={
            'username': 'newuser1',
            'password': 'NewUser123',
            'role': 'editor'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'created successfully' in resp.data.lower()

    def test_create_user_short_username(self, client, web_admin_user):
        """Short username is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post('/api/auth/admin/users', data={
            'username': 'ab',
            'password': 'Short12',
            'role': 'viewer'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Username must be 3-64 characters' in resp.data

    def test_create_user_weak_password(self, client, web_admin_user):
        """Weak password is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post('/api/auth/admin/users', data={
            'username': 'newuser2',
            'password': 'short',
            'role': 'viewer'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'at least 8' in resp.data.lower() or b'Password' in resp.data

    def test_create_user_duplicate_username(self, client, web_admin_user):
        """Duplicate username is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        # First create
        client.post('/api/auth/admin/users', data={
            'username': 'dupuser',
            'password': TEST_PASSWORD,
            'role': 'viewer'
        }, follow_redirects=True)
        # Try duplicate
        resp = client.post('/api/auth/admin/users', data={
            'username': 'dupuser',
            'password': TEST_PASSWORD,
            'role': 'viewer'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'already taken' in resp.data.lower()

    def test_create_user_invalid_role(self, client, web_admin_user):
        """Invalid role is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post('/api/auth/admin/users', data={
            'username': 'badroleuser',
            'password': TEST_PASSWORD,
            'role': 'superadmin'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid role' in resp.data

    def test_non_admin_cannot_create_user(self, client, web_editor_user):
        """Editor cannot create users via web UI."""
        _login_web(client, web_editor_user['username'], web_editor_user['password'])
        resp = client.post('/api/auth/admin/users', data={
            'username': 'hacker',
            'password': TEST_PASSWORD,
            'role': 'admin'
        }, follow_redirects=False)
        # Redirected to index with 302
        assert resp.status_code == 302
        assert resp.location == '/' or '/api/auth/signin' in resp.location

    def test_unauthenticated_cannot_create_user(self, client):
        """Unauthenticated user cannot create users."""
        resp = client.post('/api/auth/admin/users', data={
            'username': 'hacker2',
            'password': TEST_PASSWORD,
            'role': 'admin'
        }, follow_redirects=False)
        # Redirected to login or index
        assert resp.status_code == 302


# ============================================================================
# Admin Update Role (Web UI) Tests
# ============================================================================

class TestAdminUpdateRole:
    def test_admin_can_update_role(self, client, web_admin_user, web_viewer_user):
        """Admin can change a user's role via web form."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_viewer_user["id"]}/role',
            data={'role': 'editor'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'role changed' in resp.data.lower() or b'updated' in resp.data.lower()

    def test_admin_cannot_demote_self(self, client, web_admin_user):
        """Admin cannot change their own role."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_admin_user["id"]}/role',
            data={'role': 'viewer'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'Cannot change your own role' in resp.data

    def test_invalid_role_update(self, client, web_admin_user, web_viewer_user):
        """Invalid role is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_viewer_user["id"]}/role',
            data={'role': 'owner'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'Invalid role' in resp.data


# ============================================================================
# Admin Reset Password (Web UI) Tests
# ============================================================================

class TestAdminResetPassword:
    def test_admin_can_reset_password(self, client, web_admin_user, web_viewer_user):
        """Admin can reset a user's password."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_viewer_user["id"]}/password',
            data={'new_password': 'NewPass123'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'Password reset' in resp.data

    def test_reset_password_weak(self, client, web_admin_user, web_viewer_user):
        """Weak new password is rejected."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_viewer_user["id"]}/password',
            data={'new_password': 'weak'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'at least 8' in resp.data.lower() or b'Password' in resp.data

    def test_reset_password_nonexistent_user(self, client, web_admin_user):
        """Resetting password for nonexistent user shows error."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            '/api/auth/admin/users/99999/password',
            data={'new_password': 'NewPass123'},
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'User not found' in resp.data

    def test_non_admin_cannot_reset_password(self, client, web_viewer_user):
        """Non-admin cannot reset passwords."""
        _login_web(client, web_viewer_user['username'], web_viewer_user['password'])
        resp = client.post(
            '/api/auth/admin/users/1/password',
            data={'new_password': 'NewPass123'},
            follow_redirects=False
        )
        # Redirected with 302
        assert resp.status_code == 302
        assert resp.location == '/' or '/api/auth/signin' in resp.location


# ============================================================================
# Admin Delete User (Web UI) Tests
# ============================================================================

class TestAdminDeleteUser:
    def test_admin_can_delete_user(self, client, web_admin_user, app):
        """Admin can delete another user."""
        with app.app_context():
            target = User(username='deleteme', role='viewer')
            target.set_password(TEST_PASSWORD)
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{target_id}/delete',
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'deleted' in resp.data.lower()

    def test_admin_cannot_delete_self(self, client, web_admin_user):
        """Admin cannot delete their own account."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            f'/api/auth/admin/users/{web_admin_user["id"]}/delete',
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'Cannot delete your own account' in resp.data

    def test_delete_nonexistent_user(self, client, web_admin_user):
        """Deleting nonexistent user shows error."""
        _login_web(client, web_admin_user['username'], web_admin_user['password'])
        resp = client.post(
            '/api/auth/admin/users/99999/delete',
            follow_redirects=True
        )
        assert resp.status_code == 200
        assert b'User not found' in resp.data


# ============================================================================
# Decorator Tests (login_required_web, admin_required_web, editor_or_admin_web)
# ============================================================================

class TestWebDecorators:
    def test_create_recipe_form_requires_login(self, client):
        """/recipes/new redirects unauthenticated users."""
        resp = client.get('/recipes/new', follow_redirects=True)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_edit_recipe_form_requires_login(self, client, app):
        """/recipes/<id>/edit redirects unauthenticated users."""
        with app.app_context():
            from app.models import Recipe
            recipe = Recipe(title='Test', instructions='Do stuff.')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = client.get(f'/recipes/{rid}/edit', follow_redirects=True)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_editor_can_access_create_recipe(self, client, web_editor_user):
        """Editor can access the create recipe form."""
        _login_web(client, web_editor_user['username'], web_editor_user['password'])
        resp = client.get('/recipes/new')
        assert resp.status_code == 200
        assert b'Create New Recipe' in resp.data

    def test_editor_can_access_edit_recipe(self, client, web_editor_user, app):
        """Editor can access the edit recipe form."""
        with app.app_context():
            from app.models import Recipe
            recipe = Recipe(title='Edit Test', instructions='Do stuff.')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        _login_web(client, web_editor_user['username'], web_editor_user['password'])
        resp = client.get(f'/recipes/{rid}/edit')
        assert resp.status_code == 200

    def test_viewer_can_see_create_recipe_form(self, client, web_viewer_user):
        """Viewer can see the create recipe form (login_required_web passes for viewers)."""
        _login_web(client, web_viewer_user['username'], web_viewer_user['password'])
        resp = client.get('/recipes/new')
        # Viewers can see the form but POST is blocked by editor_or_admin_web
        assert resp.status_code == 200
        assert b'Create New Recipe' in resp.data
