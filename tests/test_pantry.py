"""Tests for PantryItem model and pantry API."""
import pytest
from datetime import datetime, timezone, timedelta
from app import db
from app.models import PantryItem


import json


class TestPantryItemModel:
    """Unit tests for the PantryItem model."""

    def test_create_pantry_item(self, app, db_session):
        """Test basic creation of a pantry item."""
        item = PantryItem(
            name="Chicken Breast",
            quantity=2.0,
            unit="lbs",
            category="Meat",
            min_quantity=1.0
        )
        db_session.add(item)
        db_session.flush()

        assert item.id is not None
        assert item.name == "Chicken Breast"
        assert item.quantity == 2.0
        assert item.unit == "lbs"
        assert item.category == "Meat"
        assert item.min_quantity == 1.0
        assert item.created_at is not None
        assert item.updated_at is not None

    def test_is_low_stock_true(self, app, db_session):
        """Test is_low_stock returns True when quantity <= min_quantity."""
        item = PantryItem(name="Flour", quantity=0.5, unit="cups", category="Pantry", min_quantity=1.0)
        db_session.add(item)
        db_session.flush()
        assert item.is_low_stock is True

    def test_is_low_stock_false(self, app, db_session):
        """Test is_low_stock returns False when quantity > min_quantity."""
        item = PantryItem(name="Sugar", quantity=5.0, unit="cups", category="Pantry", min_quantity=1.0)
        db_session.add(item)
        db_session.flush()
        assert item.is_low_stock is False

    def test_is_low_stock_zero_min(self, app, db_session):
        """Test is_low_stock returns False when min_quantity is 0."""
        item = PantryItem(name="Salt", quantity=0.5, unit="cups", category="Spices", min_quantity=0)
        db_session.add(item)
        db_session.flush()
        assert item.is_low_stock is False

    def test_days_until_expiry_no_date(self, app, db_session):
        """Test days_until_expiry returns None when expiry_date is None."""
        item = PantryItem(name="Olive Oil", quantity=1.0, unit="bottle", category="Pantry")
        db_session.add(item)
        db_session.flush()
        assert item.days_until_expiry is None

    def test_days_until_expiry_future(self, app, db_session):
        """Test days_until_expiry returns positive int for future date."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        item = PantryItem(name="Canned Tomatoes", quantity=6.0, unit="cans", category="Pantry", expiry_date=future)
        db_session.add(item)
        db_session.flush()
        assert item.days_until_expiry == 30 or item.days_until_expiry == 29  # SQLite datetime precision

    def test_days_until_expiry_past(self, app, db_session):
        """Test days_until_expiry returns negative int for past date."""
        past = datetime.now(timezone.utc) - timedelta(days=5)
        item = PantryItem(name="Milk", quantity=1.0, unit="gallon", category="Dairy", expiry_date=past)
        db_session.add(item)
        db_session.flush()
        assert item.days_until_expiry == -5 or item.days_until_expiry == -6  # SQLite datetime precision

    def test_to_dict(self, app, db_session):
        """Test serialization to dictionary."""
        item = PantryItem(name="Rice", quantity=10.0, unit="lbs", category="Pantry")
        db_session.add(item)
        db_session.flush()

        d = item.to_dict()
        assert d['name'] == "Rice"
        assert d['quantity'] == 10.0
        assert d['unit'] == "lbs"
        assert d['category'] == "Pantry"
        assert d['is_low_stock'] is False
        assert d['days_until_expiry'] is None
        assert 'id' in d
        assert 'created_at' in d
        assert 'updated_at' in d

    def test_min_quantity_default(self, app, db_session):
        """Test min_quantity defaults to 0."""
        item = PantryItem(name="Butter", quantity=2.0, unit="sticks", category="Dairy")
        db_session.add(item)
        db_session.flush()
        assert item.min_quantity == 0

    def test_quantity_default(self, app, db_session):
        """Test quantity defaults to 0."""
        item = PantryItem(name="Eggs", unit="dozen", category="Dairy")
        db_session.add(item)
        db_session.flush()
        assert item.quantity == 0

    def test_name_unique_constraint(self, app, db_session):
        """Test that name is unique."""
        item1 = PantryItem(name="Tomato Sauce", quantity=2.0, unit="cans", category="Pantry")
        db_session.add(item1)
        db_session.flush()

        item2 = PantryItem(name="Tomato Sauce", quantity=1.0, unit="jar", category="Pantry")
        db_session.add(item2)
        with pytest.raises(Exception):
            db_session.flush()


class TestPantryAPI:
    """Tests for the Pantry API endpoints."""

    @pytest.fixture
    def pantry_admin_headers(self, app, client):
        """Create admin user and return JWT auth headers for write operations."""
        from app.auth import User
        with app.app_context():
            admin = User(username='pantryadmin', role='admin')
            admin.set_password('TestPass123')
            db.session.add(admin)
            db.session.commit()
        resp = client.post('/api/auth/login', json={
            'username': 'pantryadmin',
            'password': 'TestPass123',
        })
        token = resp.get_json()['access_token']
        return {'Authorization': f'Bearer {token}'}

    def test_list_pantry_items_empty(self, client):
        """GET /api/pantry/items returns empty list."""
        resp = client.get('/api/pantry/items')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_pantry_items_by_category(self, client, db_session):
        """GET /api/pantry/items?category=Produce filters by category."""
        from app.models import PantryItem
        items = [
            PantryItem(name="Apples", quantity=5, unit="pieces", category="Produce"),
            PantryItem(name="Chicken", quantity=2, unit="lbs", category="Meat"),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()

        resp = client.get('/api/pantry/items?category=Produce')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Apples'

    def test_create_pantry_item(self, client, pantry_admin_headers):
        """POST /api/pantry/items creates a new item."""
        resp = client.post('/api/pantry/items', json={
            'name': 'Flour',
            'quantity': 5.0,
            'unit': 'cups',
            'category': 'Pantry',
            'min_quantity': 1.0,
        }, headers=pantry_admin_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Flour'
        assert data['quantity'] == 5.0
        assert data['unit'] == 'cups'
        assert data['category'] == 'Pantry'
        assert data['is_low_stock'] is False

    def test_create_pantry_item_duplicate(self, client, db_session, pantry_admin_headers):
        """POST /api/pantry/items with duplicate name returns 409."""
        from app.models import PantryItem
        db_session.add(PantryItem(name="Tomato Sauce", quantity=2.0, unit="cans", category="Pantry"))
        db_session.commit()

        resp = client.post('/api/pantry/items', json={
            'name': 'Tomato Sauce',
            'quantity': 1.0,
            'unit': 'jar',
            'category': 'Pantry',
        }, headers=pantry_admin_headers)
        assert resp.status_code == 409
        assert 'already exists' in resp.get_json()['error']

    def test_create_pantry_item_missing_name(self, client, pantry_admin_headers):
        """POST /api/pantry/items without name returns 400."""
        resp = client.post('/api/pantry/items', json={'quantity': 2.0}, headers=pantry_admin_headers)
        assert resp.status_code == 400

    def test_update_pantry_item(self, client, db_session, pantry_admin_headers):
        """PUT /api/pantry/items/<id> updates an item."""
        from app.models import PantryItem
        item = PantryItem(name="Sugar", quantity=2.0, unit="cups", category="Pantry")
        db_session.add(item)
        db_session.commit()

        resp = client.put(f'/api/pantry/items/{item.id}', json={
            'quantity': 1.0,
            'notes': 'Almost out',
        }, headers=pantry_admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 1.0
        assert data['notes'] == 'Almost out'

    def test_update_pantry_item_not_found(self, client, pantry_admin_headers):
        """PUT /api/pantry/items/<id> for non-existent returns 404."""
        resp = client.put('/api/pantry/items/99999', json={'quantity': 1.0}, headers=pantry_admin_headers)
        assert resp.status_code == 404

    def test_delete_pantry_item(self, client, db_session, pantry_admin_headers):
        """DELETE /api/pantry/items/<id> removes an item."""
        from app.models import PantryItem
        item = PantryItem(name="Old Spice", quantity=1.0, unit="jar", category="Spices")
        db_session.add(item)
        db_session.commit()

        resp = client.delete(f'/api/pantry/items/{item.id}', headers=pantry_admin_headers)
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = client.get('/api/pantry/items')
        assert len(resp2.get_json()) == 0

    def test_delete_pantry_item_not_found(self, client, pantry_admin_headers):
        """DELETE /api/pantry/items/<id> for non-existent returns 404."""
        resp = client.delete('/api/pantry/items/99999', headers=pantry_admin_headers)
        assert resp.status_code == 404

    def test_deduct_quantity(self, client, db_session, pantry_admin_headers):
        """POST /api/pantry/items/<id>/deduct reduces quantity."""
        from app.models import PantryItem
        item = PantryItem(name="Flour", quantity=10.0, unit="cups", category="Pantry")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f'/api/pantry/items/{item.id}/deduct', json={'quantity': 3.0}, headers=pantry_admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 7.0

    def test_deduct_quantity_negative_result(self, client, db_session, pantry_admin_headers):
        """POST /api/pantry/items/<id>/deduct cannot go below 0."""
        from app.models import PantryItem
        item = PantryItem(name="Eggs", quantity=2.0, unit="dozen", category="Dairy")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f'/api/pantry/items/{item.id}/deduct', json={'quantity': 5.0}, headers=pantry_admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 0  # Clamped to 0

    def test_deduct_quantity_not_found(self, client, pantry_admin_headers):
        """POST /api/pantry/items/<id>/deduct for non-existent returns 404."""
        resp = client.post('/api/pantry/items/99999/deduct', json={'quantity': 1.0}, headers=pantry_admin_headers)
        assert resp.status_code == 404

    def test_low_stock_endpoint(self, client, db_session):
        """GET /api/pantry/low-stock returns items below min_quantity."""
        from app.models import PantryItem
        items = [
            PantryItem(name="Rice", quantity=0.5, unit="cups", category="Pantry", min_quantity=1.0),
            PantryItem(name="Pasta", quantity=5.0, unit="boxes", category="Pantry", min_quantity=2.0),
            PantryItem(name="Olive Oil", quantity=2.0, unit="bottles", category="Pantry", min_quantity=1.0),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()

        resp = client.get('/api/pantry/low-stock')
        assert resp.status_code == 200
        data = resp.get_json()
        names = [item['name'] for item in data]
        assert 'Rice' in names          # 0.5 <= 1.0
        assert 'Olive Oil' not in names # 2.0 > 1.0
        assert 'Pasta' not in names     # 5.0 > 2.0

    def test_ingredients_to_pantry(self, client, db_session, pantry_admin_headers):
        """POST /api/pantry/ingredients-to-pantry imports recipe ingredients."""
        from app.models import Recipe
        recipe = Recipe(
            title="Test Pasta",
            instructions="Boil water.",
            ingredients="1 lb pasta\n2 cups tomato sauce\n1 tbsp olive oil",
        )
        db_session.add(recipe)
        db_session.commit()

        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': recipe.id}, headers=pantry_admin_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['count'] == 3
        names = [item['name'] for item in data['items']]
        assert 'pasta' in names
        assert 'tomato sauce' in names
        assert 'olive oil' in names

    def test_ingredients_to_pantry_no_ingredients(self, client, db_session, pantry_admin_headers):
        """POST /api/pantry/ingredients-to-pantry on recipe without ingredients."""
        from app.models import Recipe
        recipe = Recipe(title="Empty", instructions="Do nothing.")
        db_session.add(recipe)
        db_session.commit()

        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': recipe.id}, headers=pantry_admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 0

    def test_ingredients_to_pantry_not_found(self, client, pantry_admin_headers):
        """POST /api/pantry/ingredients-to-pantry for non-existent recipe."""
        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': 99999}, headers=pantry_admin_headers)
        assert resp.status_code == 404

    def test_ingredients_to_pantry_no_recipe_id(self, client, pantry_admin_headers):
        """POST /api/pantry/ingredients-to-pantry without recipe_id returns 400."""
        resp = client.post('/api/pantry/ingredients-to-pantry', json={}, headers=pantry_admin_headers)
        assert resp.status_code == 400


class TestPantryWeb:
    """Tests for the pantry web UI."""

    def test_pantry_page_loads(self, client):
        """GET /pantry returns 200."""
        resp = client.get('/pantry')
        assert resp.status_code == 200

    def test_pantry_page_content(self, client, db_session):
        """GET /pantry shows the pantry page with title."""
        from app.models import PantryItem
        item = PantryItem(name="Chicken", quantity=2.0, unit="lbs", category="Meat")
        db_session.add(item)
        db_session.commit()

        resp = client.get('/pantry')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Pantry Inventory' in html
