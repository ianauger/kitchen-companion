import pytest
from config import MAX_NOTE_LENGTH


def _get_auth_header(client, admin_user):
    """Helper: get JWT auth header for API calls."""
    resp = client.post('/api/auth/login', json={
        'username': admin_user['username'],
        'password': admin_user['password']
    })
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_create_note_success(client, sample_recipe, admin_user):
    headers = _get_auth_header(client, admin_user)
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': 'This tastes amazing!'},
        headers=headers
    )
    assert response.status_code == 201
    assert b'This tastes amazing!' in response.data

def test_create_note_empty_content(client, sample_recipe, admin_user):
    headers = _get_auth_header(client, admin_user)
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': '   '},
        headers=headers
    )
    assert response.status_code == 400
    assert b'Content is required' in response.data

def test_create_note_too_long(client, sample_recipe, admin_user):
    headers = _get_auth_header(client, admin_user)
    long_content = 'a' * (MAX_NOTE_LENGTH + 1)
    headers = _get_auth_header(client, admin_user)
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': long_content},
        headers=headers
    )
    assert response.status_code == 400
    assert b'exceeds maximum length' in response.data
