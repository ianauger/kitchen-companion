"""Tests for recipe API endpoints."""
import pytest
import json
from app.models import Recipe, Tag
from app.auth import User
from app import db

# Valid test password that meets complexity requirements
TEST_PASSWORD = 'Password123'


def _ensure_admin(client, app):
    """Create an admin user and return auth headers."""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', role='admin')
            admin.set_password(TEST_PASSWORD)
            db.session.add(admin)
            db.session.commit()
    resp = client.post('/api/auth/login',
                       data=json.dumps({'username': 'admin', 'password': TEST_PASSWORD}),
                       content_type='application/json')
    token = json.loads(resp.data)['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_add_tag_api(client, app, db_session):
    """Test that tags can be added via the POST /api/recipes/<id>/tags endpoint."""
    headers = _ensure_admin(client, app)

    # Setup: Create a recipe (authenticated)
    resp = client.post('/api/recipes',
                       data=json.dumps({'title': 'Test Recipe', 'instructions': 'Some instructions'}),
                       content_type='application/json', headers=headers)
    recipe_id = json.loads(resp.data)['id']

    # 1. Add a new tag
    response = client.post(f'/api/recipes/{recipe_id}/tags',
                          json={'tag': '  Delicious  '}, headers=headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Delicious'

    # Verify it's associated with the recipe
    with app.app_context():
        recipe = db.session.get(Recipe, recipe_id)
        assert any(tag.name == 'Delicious' for tag in recipe.tags)

    # 2. Add the same tag again (should not create duplicate association)
    response = client.post(f'/api/recipes/{recipe_id}/tags',
                          json={'tag': 'delicious'}, headers=headers)
    assert response.status_code == 201

    with app.app_context():
        recipe = db.session.get(Recipe, recipe_id)
        tags_list = [tag.name for tag in recipe.tags]
        assert tags_list.count('Delicious') == 1

    # 3. Add a different tag
    response = client.post(f'/api/recipes/{recipe_id}/tags',
                          json={'tag': 'Quick'}, headers=headers)
    assert response.status_code == 201
    
    with app.app_context():
        recipe = db.session.get(Recipe, recipe_id)
        assert any(tag.name == 'Quick' for tag in recipe.tags)


def test_add_tag_invalid_requests(client, app, db_session):
    """Test invalid requests to the tag API."""
    headers = _ensure_admin(client, app)

    # Setup: Create a recipe
    resp = client.post('/api/recipes',
                       data=json.dumps({'title': 'Test Recipe', 'instructions': 'Some instructions'}),
                       content_type='application/json', headers=headers)
    recipe_id = json.loads(resp.data)['id']

    # Missing tag name
    response = client.post(f'/api/recipes/{recipe_id}/tags',
                          json={}, headers=headers)
    assert response.status_code == 400

    # Empty tag name
    response = client.post(f'/api/recipes/{recipe_id}/tags',
                          json={'tag': '   '}, headers=headers)
    assert response.status_code == 400

    # Non-existent recipe
    response = client.post('/api/recipes/99999/tags',
                          json={'tag': 'test'}, headers=headers)
    assert response.status_code == 404


def test_create_recipe_authenticated(client, app):
    """Test creating a recipe with authentication."""
    headers = _ensure_admin(client, app)

    resp = client.post('/api/recipes',
                       data=json.dumps({
                           'title': 'Auth Test Recipe',
                           'instructions': '1. Do things.\n2. Eat.',
                           'cooking_time': 20,
                           'prep_time': 10,
                           'servings': 4,
                           'difficulty': 'easy',
                           'tags': [
                               {'name': 'Italian', 'tag_type': 'cuisine'},
                               {'name': 'vegetarian', 'tag_type': 'protein'},
                           ]
                       }),
                       content_type='application/json', headers=headers)
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data['title'] == 'Auth Test Recipe'
    assert data['cooking_time'] == 20
    assert len(data['tags']) == 2


def test_create_recipe_unauthenticated(client):
    """Test creating a recipe without auth is rejected."""
    resp = client.post('/api/recipes',
                       data=json.dumps({
                           'title': 'No Auth Recipe',
                           'instructions': '1. Test.'
                       }),
                       content_type='application/json')
    assert resp.status_code == 401


def test_create_recipe_viewer_denied(client, app):
    """Test that viewers cannot create recipes."""
    headers = _ensure_admin(client, app)

    # Create a viewer
    client.post('/api/auth/register',
               data=json.dumps({'username': 'viewer', 'password': TEST_PASSWORD}),
               content_type='application/json')
    resp = client.post('/api/auth/login',
                      data=json.dumps({'username': 'viewer', 'password': TEST_PASSWORD}),
                      content_type='application/json')
    vtoken = json.loads(resp.data)['access_token']
    vheaders = {'Authorization': f'Bearer {vtoken}'}

    resp = client.post('/api/recipes',
                       data=json.dumps({'title': 'Viewer Recipe', 'instructions': '1. X'}),
                       content_type='application/json', headers=vheaders)
    assert resp.status_code == 403


def test_get_recipes_public(client):
    """Test that listing recipes is public (no auth required)."""
    resp = client.get('/api/recipes')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'recipes' in data
    assert 'pagination' in data
