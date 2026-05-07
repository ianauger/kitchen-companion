"""Tests for API key authentication: X-API-Key header bypass for write endpoints."""
import pytest
import json
from app.auth import User
from app import db

TEST_PASSWORD = 'Password123'


def _register_user(app, username, role):
    """Create a user with the given role."""
    with app.app_context():
        user = User(username=username, role=role)
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user


def _login(client, username):
    resp = client.post('/api/auth/login',
                       data=json.dumps({'username': username, 'password': TEST_PASSWORD}),
                       content_type='application/json')
    return json.loads(resp.data)['access_token']


def _generate_api_key(client, token, user_id):
    resp = client.post(f'/api/auth/users/{user_id}/api-key',
                       headers={'Authorization': f'Bearer {token}'})
    return json.loads(resp.data).get('api_key')


class TestApiKeyAuthBypass:
    """Test that X-API-Key header works for editor_or_admin-protected endpoints."""

    def test_create_recipe_with_api_key(self, client, app):
        """POST /api/recipes with X-API-Key header works."""
        _register_user(app, 'apieditor', 'editor')
        token = _login(client, 'apieditor')

        # Get user ID
        with app.app_context():
            user = User.query.filter_by(username='apieditor').first()
            uid = user.id

        api_key = _generate_api_key(client, token, uid)
        assert api_key is not None

        # Submit recipe with API key (no JWT)
        resp = client.post('/api/recipes',
                          json={
                              'title': 'API Key Recipe',
                              'instructions': '1. Test.',
                          },
                          headers={'X-API-Key': api_key})
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['title'] == 'API Key Recipe'

    def test_viewer_api_key_cannot_write(self, client, app):
        """X-API-Key from a viewer user cannot create recipes."""
        _register_user(app, 'apiviewer', 'viewer')
        token = _login(client, 'apiviewer')

        with app.app_context():
            user = User.query.filter_by(username='apiviewer').first()
            uid = user.id

        api_key = _generate_api_key(client, token, uid)

        resp = client.post('/api/recipes',
                          json={'title': 'Nope', 'instructions': '1. Nope.'},
                          headers={'X-API-Key': api_key})
        assert resp.status_code == 403

    def test_revoked_api_key_rejected(self, client, app):
        """A revoked API key is rejected."""
        _register_user(app, 'revoker', 'editor')
        token = _login(client, 'revoker')

        with app.app_context():
            user = User.query.filter_by(username='revoker').first()
            uid = user.id

        api_key = _generate_api_key(client, token, uid)

        # Revoke it
        client.delete(f'/api/auth/users/{uid}/api-key',
                     headers={'Authorization': f'Bearer {token}'})

        # Try with revoked key
        resp = client.post('/api/recipes',
                          json={'title': 'No', 'instructions': '1. No.'},
                          headers={'X-API-Key': api_key})
        assert resp.status_code != 201

    def test_missing_api_key_falls_through_to_jwt(self, client, app):
        """Without X-API-Key or JWT, the endpoint returns 401."""
        resp = client.post('/api/recipes',
                          json={'title': 'Unauthorized', 'instructions': '1. Test.'})
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert 'Missing' in data.get('msg', '')

    def test_fake_api_key_rejected(self, client, app):
        """A completely invalid API key is rejected."""
        resp = client.post('/api/recipes',
                          json={'title': 'Fake', 'instructions': '1. Fake.'},
                          headers={'X-API-Key': 'sk-this-is-totally-made-up'})
        assert resp.status_code == 401


class TestApiKeyEndpoints:
    """Test the /api/auth/users/:id/api-key endpoints."""

    def test_admin_can_generate_key_for_other_user(self, client, app):
        """An admin can generate an API key for any user."""
        _register_user(app, 'targetuser', 'editor')
        admin_user = _register_user(app, 'superadmin', 'admin')
        admin_token = _login(client, 'superadmin')

        with app.app_context():
            target = User.query.filter_by(username='targetuser').first()

        resp = client.post(f'/api/auth/users/{target.id}/api-key',
                          headers={'Authorization': f'Bearer {admin_token}'})
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert 'api_key' in data
        assert data['api_key'].startswith('sk-')
        assert data['user']['has_api_key'] is True

    def test_user_can_generate_own_key(self, client, app):
        """A user can generate their own API key."""
        _register_user(app, 'selfkey', 'editor')
        token = _login(client, 'selfkey')

        with app.app_context():
            user = User.query.filter_by(username='selfkey').first()

        resp = client.post(f'/api/auth/users/{user.id}/api-key',
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 201
        assert 'api_key' in json.loads(resp.data)

    def test_user_cannot_generate_key_for_others(self, client, app):
        """A non-admin cannot generate an API key for another user."""
        _register_user(app, 'alice', 'editor')
        _register_user(app, 'bob', 'editor')
        bob_token = _login(client, 'bob')

        with app.app_context():
            alice = User.query.filter_by(username='alice').first()

        resp = client.post(f'/api/auth/users/{alice.id}/api-key',
                          headers={'Authorization': f'Bearer {bob_token}'})
        assert resp.status_code == 403

    def test_revoke_nonexistent_key(self, client, app):
        """Revoking when no key exists returns 404."""
        _register_user(app, 'nokeyuser', 'editor')
        token = _login(client, 'nokeyuser')

        with app.app_context():
            user = User.query.filter_by(username='nokeyuser').first()

        resp = client.delete(f'/api/auth/users/{user.id}/api-key',
                            headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 404

    def test_api_key_never_shown_again(self, client, app):
        """After generating a key, subsequent GET /me does not reveal the raw key."""
        _register_user(app, 'secrettest', 'editor')
        token = _login(client, 'secrettest')

        with app.app_context():
            user = User.query.filter_by(username='secrettest').first()

        resp = client.post(f'/api/auth/users/{user.id}/api-key',
                          headers={'Authorization': f'Bearer {token}'})
        raw_from_gen = json.loads(resp.data)['api_key']

        # GET /me should NOT contain the raw key
        resp = client.get('/api/auth/me',
                         headers={'Authorization': f'Bearer {token}'})
        user_data = json.loads(resp.data)
        assert 'api_key' not in user_data
        assert 'api_key_hash' not in user_data
        assert raw_from_gen not in json.dumps(user_data)
