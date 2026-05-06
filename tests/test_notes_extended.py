"""Extended tests for notes API: RBAC enforcement, update, and delete."""
import pytest
import json
from app.auth import User
from app.models import Note
from app import db
from config import MAX_NOTE_LENGTH

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
    return data.get('access_token')


def _auth_header(token):
    return {'Authorization': f'Bearer {token}'} if token else {}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def admin_headers(app, client):
    """Create admin, return auth headers."""
    with app.app_context():
        admin = User(username='notesadmin', role='admin')
        admin.set_password(TEST_PASSWORD)
        db.session.add(admin)
        db.session.commit()
    token = _login(client, 'notesadmin', TEST_PASSWORD)
    return _auth_header(token)


@pytest.fixture
def editor_headers(app, client, admin_headers):
    """Create editor, return auth headers."""
    _register(client, 'noteseditor', TEST_PASSWORD, role='viewer')
    client.put('/api/auth/users/2/role',
               data=json.dumps({'role': 'editor'}),
               content_type='application/json',
               headers=admin_headers)
    token = _login(client, 'noteseditor', TEST_PASSWORD)
    return _auth_header(token)


@pytest.fixture
def viewer_headers(app, client):
    """Create viewer, return auth headers."""
    _register(client, 'notesviewer', TEST_PASSWORD, role='viewer')
    token = _login(client, 'notesviewer', TEST_PASSWORD)
    return _auth_header(token)


@pytest.fixture
def recipe_id(app, client, admin_headers):
    """Create a recipe, return its ID."""
    resp = client.post('/api/recipes',
                       data=json.dumps({'title': 'Notes Test Recipe', 'instructions': '1. Cook.'}),
                       content_type='application/json',
                       headers=admin_headers)
    return json.loads(resp.data)['id']


@pytest.fixture
def note_id(app, client, admin_headers, recipe_id):
    """Create a note, return its ID."""
    resp = client.post(f'/api/recipes/{recipe_id}/notes',
                       data=json.dumps({'content': 'Original note.'}),
                       content_type='application/json',
                       headers=admin_headers)
    return json.loads(resp.data)['id']


# ============================================================================
# Create Note RBAC Tests
# ============================================================================

class TestCreateNoteRBAC:
    def test_editor_can_create_note(self, client, editor_headers, recipe_id):
        """Editor can create a note."""
        resp = client.post(f'/api/recipes/{recipe_id}/notes',
                          json={'content': 'Editor note'},
                          headers=editor_headers)
        assert resp.status_code == 201

    def test_viewer_cannot_create_note(self, client, viewer_headers, recipe_id):
        """Viewer gets 403 when creating a note."""
        resp = client.post(f'/api/recipes/{recipe_id}/notes',
                          json={'content': 'Viewer note'},
                          headers=viewer_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_note(self, client, recipe_id):
        """Unauthenticated gets 401 when creating a note."""
        resp = client.post(f'/api/recipes/{recipe_id}/notes',
                          json={'content': 'Anonymous note'},
                          headers=_auth_header(None))
        assert resp.status_code == 401

    def test_create_note_nonexistent_recipe(self, client, admin_headers):
        """Creating note on nonexistent recipe returns 404."""
        resp = client.post('/api/recipes/99999/notes',
                          json={'content': 'Note on nothing'},
                          headers=admin_headers)
        assert resp.status_code == 404

    def test_create_note_missing_content(self, client, admin_headers, recipe_id):
        """Missing content field returns 400."""
        resp = client.post(f'/api/recipes/{recipe_id}/notes',
                           json={},
                           headers=admin_headers)
        assert resp.status_code == 400


# ============================================================================
# Get Notes Tests
# ============================================================================

class TestGetNotes:
    def test_get_notes_public(self, client, recipe_id, note_id):
        """Getting notes is public (no auth required)."""
        resp = client.get(f'/api/recipes/{recipe_id}/notes')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data) >= 1

    def test_get_notes_empty_recipe(self, client, recipe_id):
        """Empty notes list returns empty array."""
        resp = client.get(f'/api/recipes/{recipe_id}/notes')
        assert resp.status_code == 200
        assert isinstance(json.loads(resp.data), list)

    def test_get_notes_nonexistent_recipe(self, client):
        """Nonexistent recipe returns 404."""
        resp = client.get('/api/recipes/99999/notes')
        assert resp.status_code == 404


# ============================================================================
# Update Note Tests
# ============================================================================

class TestUpdateNote:
    def test_admin_can_update_note(self, client, admin_headers, note_id):
        """Admin can update a note."""
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': 'Updated by admin.'},
                         headers=admin_headers)
        assert resp.status_code == 200
        assert json.loads(resp.data)['content'] == 'Updated by admin.'

    def test_editor_can_update_note(self, client, editor_headers, note_id):
        """Editor can update a note."""
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': 'Updated by editor.'},
                         headers=editor_headers)
        assert resp.status_code == 200

    def test_viewer_cannot_update_note(self, client, viewer_headers, note_id):
        """Viewer gets 403 when updating a note."""
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': 'Viewer update attempt.'},
                         headers=viewer_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_update_note(self, client, note_id):
        """Unauthenticated gets 401 when updating a note."""
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': 'Anonymous update'},
                         headers=_auth_header(None))
        assert resp.status_code == 401

    def test_update_nonexistent_note(self, client, admin_headers):
        """Updating nonexistent note returns 404."""
        resp = client.put('/api/notes/99999',
                         json={'content': 'Nowhere note.'},
                         headers=admin_headers)
        assert resp.status_code == 404

    def test_update_note_empty_content(self, client, admin_headers, note_id):
        """Empty content returns 400."""
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': '   '},
                         headers=admin_headers)
        assert resp.status_code == 400

    def test_update_note_missing_content(self, client, admin_headers, note_id):
        """Missing content field returns 400."""
        resp = client.put(f'/api/notes/{note_id}',
                          json={},
                          headers=admin_headers)
        assert resp.status_code == 400

    def test_update_note_too_long(self, client, admin_headers, note_id):
        """Content exceeding max length returns 400."""
        long_content = 'a' * (MAX_NOTE_LENGTH + 1)
        resp = client.put(f'/api/notes/{note_id}',
                         json={'content': long_content},
                         headers=admin_headers)
        assert resp.status_code == 400
        assert b'exceeds maximum length' in resp.data


# ============================================================================
# Delete Note Tests
# ============================================================================

class TestDeleteNote:
    def test_admin_can_delete_note(self, client, admin_headers, app, recipe_id):
        """Admin can delete a note."""
        # Create a note to delete
        resp = client.post(f'/api/recipes/{recipe_id}/notes',
                          json={'content': 'Delete me.'},
                          headers=admin_headers)
        nid = json.loads(resp.data)['id']
        resp = client.delete(f'/api/notes/{nid}', headers=admin_headers)
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get(f'/api/recipes/{recipe_id}/notes')
        assert all(n['id'] != nid for n in json.loads(resp.data))

    def test_editor_cannot_delete_note(self, client, editor_headers, note_id):
        """Editor gets 403 when deleting a note."""
        resp = client.delete(f'/api/notes/{note_id}', headers=editor_headers)
        assert resp.status_code == 403

    def test_viewer_cannot_delete_note(self, client, viewer_headers, note_id):
        """Viewer gets 403 when deleting a note."""
        resp = client.delete(f'/api/notes/{note_id}', headers=viewer_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_delete_note(self, client, note_id):
        """Unauthenticated gets 401 when deleting."""
        resp = client.delete(f'/api/notes/{note_id}')
        assert resp.status_code == 401

    def test_delete_nonexistent_note(self, client, admin_headers):
        """Deleting nonexistent note returns 404."""
        resp = client.delete('/api/notes/99999', headers=admin_headers)
        assert resp.status_code == 404
