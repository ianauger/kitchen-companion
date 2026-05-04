"""Tests for shopping list API endpoints."""
import pytest
import json
from app.models import Recipe, ShoppingItem
from app.auth import User
from app import db

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


def test_get_empty_shopping_list(client):
    """GET /api/shopping-items returns empty array."""
    response = client.get('/api/shopping-items')
    assert response.status_code == 200
    assert response.get_json() == []


def test_add_shopping_items(client, app, sample_recipe):
    """POST /api/shopping-items adds items."""
    headers = _ensure_admin(client, app)
    response = client.post('/api/shopping-items',
                          json={
                              'items': [
                                  {'name': '2 cups flour', 'recipe_id': sample_recipe},
                                  {'name': '1 cup sugar', 'recipe_id': None},
                              ]
                          }, headers=headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data['count'] == 2
    assert len(data['items']) == 2
    assert data['items'][0]['name'] == '2 cups flour'
    assert data['items'][0]['recipe_id'] == sample_recipe


def test_add_shopping_items_skips_empty_names(client, app):
    """Empty names are skipped."""
    headers = _ensure_admin(client, app)
    response = client.post('/api/shopping-items',
                          json={
                              'items': [
                                  {'name': '   ', 'recipe_id': None},
                                  {'name': 'valid item', 'recipe_id': None},
                              ]
                          }, headers=headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data['count'] == 1


def test_add_shopping_items_skips_duplicates(client, app):
    """Duplicate unpurchased items are skipped."""
    headers = _ensure_admin(client, app)
    client.post('/api/shopping-items',
               json={'items': [{'name': 'eggs', 'recipe_id': None}]},
               headers=headers)
    response = client.post('/api/shopping-items',
                          json={'items': [{'name': 'eggs', 'recipe_id': None}]},
                          headers=headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data['count'] == 0


def test_toggle_purchased(client, app):
    """PUT /api/shopping-items/<id> toggles purchased."""
    headers = _ensure_admin(client, app)
    r = client.post('/api/shopping-items',
                   json={'items': [{'name': 'milk', 'recipe_id': None}]},
                   headers=headers)
    item_id = r.get_json()['items'][0]['id']

    r = client.put(f'/api/shopping-items/{item_id}',
                  json={'purchased': True}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['purchased'] is True

    r = client.put(f'/api/shopping-items/{item_id}',
                  json={'purchased': False}, headers=headers)
    assert r.get_json()['purchased'] is False


def test_delete_shopping_item(client, app):
    """DELETE /api/shopping-items/<id> removes item."""
    headers = _ensure_admin(client, app)
    r = client.post('/api/shopping-items',
                   json={'items': [{'name': 'butter', 'recipe_id': None}]},
                   headers=headers)
    item_id = r.get_json()['items'][0]['id']

    r = client.delete(f'/api/shopping-items/{item_id}', headers=headers)
    assert r.status_code == 204

    r = client.get('/api/shopping-items')
    assert r.get_json() == []


def test_clear_purchased(client, app):
    """POST /api/shopping-items/clear-purchased removes purchased items."""
    headers = _ensure_admin(client, app)
    r = client.post('/api/shopping-items',
                   json={
                       'items': [
                           {'name': 'keep me', 'recipe_id': None},
                           {'name': 'remove me', 'recipe_id': None},
                       ]
                   }, headers=headers)
    items = r.get_json()['items']
    bought_id = items[1]['id']
    client.put(f'/api/shopping-items/{bought_id}',
              json={'purchased': True}, headers=headers)

    r = client.post('/api/shopping-items/clear-purchased', headers=headers)
    assert r.get_json()['deleted'] == 1

    r = client.get('/api/shopping-items')
    remaining = r.get_json()
    assert len(remaining) == 1
    assert remaining[0]['name'] == 'keep me'


def test_filter_by_purchased(client, app):
    """GET /api/shopping-items?purchased=false filters correctly."""
    headers = _ensure_admin(client, app)
    r = client.post('/api/shopping-items',
                   json={
                       'items': [
                           {'name': 'unbought', 'recipe_id': None},
                           {'name': 'bought', 'recipe_id': None},
                       ]
                   }, headers=headers)
    bought_id = r.get_json()['items'][1]['id']
    client.put(f'/api/shopping-items/{bought_id}',
              json={'purchased': True}, headers=headers)

    r = client.get('/api/shopping-items?purchased=false')
    items = r.get_json()
    assert len(items) == 1
    assert items[0]['name'] == 'unbought'


def test_shopping_list_page_renders(client):
    """The /shopping-list page loads."""
    r = client.get('/shopping-list')
    assert r.status_code == 200
    assert b'Shopping List' in r.data


def test_add_to_list_from_recipe_page(client, app, sample_recipe):
    """Adding items from recipe page with recipe_id works."""
    headers = _ensure_admin(client, app)
    r = client.post('/api/shopping-items',
                   json={'items': [{'name': 'pasta', 'recipe_id': sample_recipe}]},
                   headers=headers)
    items = r.get_json()['items']
    r = client.get('/api/shopping-items')
    data = r.get_json()
    assert len(data) == 1
    assert data[0]['recipe_title'] == 'Test Pasta'
    assert data[0]['recipe_id'] == sample_recipe


def test_shopping_list_page_has_sidebar_link(client):
    """The shopping list link appears on every page."""
    r = client.get('/')
    assert r.status_code == 200
    assert b'/shopping-list' in r.data
