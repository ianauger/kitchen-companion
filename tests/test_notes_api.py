import pytest
from config import MAX_NOTE_LENGTH

def test_create_note_success(client, sample_recipe):
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': 'This tastes amazing!'}
    )
    assert response.status_code == 201
    assert b'This tastes amazing!' in response.data

def test_create_note_empty_content(client, sample_recipe):
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': '   '}
    )
    assert response.status_code == 400
    assert b'Content is required' in response.data

def test_create_note_too_long(client, sample_recipe):
    long_content = 'a' * (MAX_NOTE_LENGTH + 1)
    response = client.post(
        f'/api/recipes/{sample_recipe}/notes',
        json={'content': long_content}
    )
    assert response.status_code == 400
    assert b'exceeds maximum length' in response.data
