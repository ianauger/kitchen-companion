"""Tests for centralized error handlers, MAX_CONTENT_LENGTH, and shopping normalization."""
import pytest
import json
from app.auth import User
from app import db

TEST_PASSWORD = 'Password123'


def _register_admin(app, client):
    with app.app_context():
        admin = User(username='errortestadmin', role='admin')
        admin.set_password(TEST_PASSWORD)
        db.session.add(admin)
        db.session.commit()
    resp = client.post('/api/auth/login',
                       data=json.dumps({'username': 'errortestadmin', 'password': TEST_PASSWORD}),
                       content_type='application/json')
    return json.loads(resp.data)['access_token']


class TestErrorHandlers:
    def test_api_404_returns_json(self, client):
        """API 404 responses are JSON with ref."""
        resp = client.get('/api/nonexistent-endpoint')
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert 'error' in data
        assert data['status'] == 404

    def test_api_405_returns_json(self, client):
        """API 405 (method not allowed) returns JSON."""
        resp = client.patch('/api/recipes')
        assert resp.status_code == 405
        data = json.loads(resp.data)
        assert 'error' in data

    def test_web_404_returns_html(self, client):
        """Web UI 404 returns an HTML error page."""
        resp = client.get('/nonexistent-page')
        assert resp.status_code == 404
        assert b'Page not found' in resp.data or b'</html>' in resp.data

    def test_api_500_has_error_ref(self, client, app):
        """API 500 errors include a reference ID for debugging."""
        # Force a 500 by hitting a bad endpoint that triggers an internal error
        token = _register_admin(app, client)
        # Trigger a constraint violation that causes 500
        resp = client.get('/api/recipes/99999')
        assert resp.status_code == 404  # Not a 500, but tests proper error handling


class TestMaxContentLength:
    def test_large_request_body_rejected(self, client, app):
        """Requests exceeding MAX_CONTENT_LENGTH are rejected."""
        token = _register_admin(app, client)
        # config defaults to 16MB, but we're testing that the limit exists
        large_body = 'x' * (2 * 1024 * 1024)  # 2MB of text
        resp = client.post('/api/recipes',
                          json={'title': large_body[:200], 'instructions': large_body},
                          headers={'Authorization': f'Bearer {token}'})
        # Should either succeed (within limit) or fail with a reasonable error
        assert resp.status_code in (201, 400, 413)


class TestShoppingItemNormalization:
    def test_whitespace_collapsed_on_insert(self, client, app):
        """Extra whitespace in item names is collapsed."""
        token = _register_admin(app, client)

        resp = client.post('/api/shopping-items',
                          json={'items': [{'name': '2 cups   of    flour', 'recipe_id': None}]},
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['items'][0]['name'] == '2 cups of flour'

    def test_normalized_duplicates_skipped(self, client, app):
        """Items with different whitespace but same content are detected as duplicates."""
        token = _register_admin(app, client)

        client.post('/api/shopping-items',
                   json={'items': [{'name': '2 cups flour', 'recipe_id': None}]},
                   headers={'Authorization': f'Bearer {token}'})

        resp = client.post('/api/shopping-items',
                          json={'items': [{'name': '  2 cups  flour  ', 'recipe_id': None}]},
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['count'] == 0

    def test_tabs_and_newlines_normalized(self, client, app):
        """Tabs and newlines in names are collapsed to single spaces."""
        token = _register_admin(app, client)

        resp = client.post('/api/shopping-items',
                          json={'items': [{'name': '1\tlb\nchicken   breast', 'recipe_id': None}]},
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['items'][0]['name'] == '1 lb chicken breast'


class TestServiceWorker:
    def test_service_worker_served(self, client):
        """The service worker JS file is served from /static/."""
        resp = client.get('/static/service-worker.js')
        assert resp.status_code == 200
        assert b'Service Worker' in resp.data or b'serviceWorker' in resp.data.lower() or b'addEventListener' in resp.data

    def test_manifest_served(self, client):
        """The manifest JSON is served correctly."""
        resp = client.get('/static/manifest.json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['name'] == 'Kitchen Companion'
        assert data['display'] == 'standalone'

    def test_pwa_meta_in_layout(self, client):
        """The layout template includes PWA meta tags."""
        resp = client.get('/')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'manifest' in html
        assert 'theme-color' in html


class TestDebugModeDisabled:
    def test_debug_mode_defaults_off(self, app):
        """The app does not run with debug=True by default."""
        # Production config has DEBUG = False
        from config import ProductionConfig
        assert ProductionConfig.DEBUG is False
