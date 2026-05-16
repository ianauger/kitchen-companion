# Pantry Inventory Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pantry inventory management system to Kitchen Companion, allowing users to track ingredient stock levels, get low-stock alerts, and import ingredients from recipes directly into their pantry.

**Architecture:** New `PantryItem` SQLAlchemy model with pantry-related routes in `routes.py`. A new `pantry.html` template with full JS interactivity (stock view grouped by category, add/edit modal, low-stock alerts, bulk import from recipes). Tests follow TDD in `tests/test_pantry.py`.

**Tech Stack:** Flask, SQLAlchemy, SQLite (dev), Jinja2, vanilla JS (no framework)

---

### Task 1: PantryItem Model

**Files:**
- Modify: `app/models.py` — add PantryItem model after existing models
- Test: `tests/test_pantry.py` — model unit tests

- [ ] **Step 1: Write the failing model tests**

```python
"""Tests for PantryItem model."""
import pytest
from datetime import datetime, timezone, timedelta
from app import db
from app.models import PantryItem


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
        assert item.days_until_expiry == 30

    def test_days_until_expiry_past(self, app, db_session):
        """Test days_until_expiry returns negative int for past date."""
        past = datetime.now(timezone.utc) - timedelta(days=5)
        item = PantryItem(name="Milk", quantity=1.0, unit="gallon", category="Dairy", expiry_date=past)
        db_session.add(item)
        db_session.flush()
        assert item.days_until_expiry == -5

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
        """Test that name is unique (case-insensitive check via unique constraint)."""
        item1 = PantryItem(name="Tomato Sauce", quantity=2.0, unit="cans", category="Pantry")
        db_session.add(item1)
        db_session.flush()

        item2 = PantryItem(name="Tomato Sauce", quantity=1.0, unit="jar", category="Pantry")
        db_session.add(item2)
        with pytest.raises(Exception):
            db_session.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryItemModel -v 2>&1`
Expected: FAIL with ImportError or no such table

- [ ] **Step 3: Implement PantryItem model in models.py**

Add the following model after the `PrepTask` model in `app/models.py`:

```python

# ── Pantry Inventory Models ─────────────────────────────────────────────

class PantryItem(db.Model):
    """An item in the user's pantry inventory.

    Attributes:
        id: Unique identifier
        name: Item name (unique)
        quantity: How much you have (default 0)
        unit: Unit of measurement (cups, lbs, pieces, etc.)
        category: Mirrors aisle categorization (Produce, Meat, etc.)
        min_quantity: Low-stock threshold (default 0 = no alert)
        purchased_date: Last time you bought it
        expiry_date: When it expires
        notes: Optional notes
        created_at, updated_at: Timestamps
    """
    __tablename__ = 'pantry_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(50), default='Other', index=True)
    min_quantity = db.Column(db.Float, default=0)
    purchased_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def is_low_stock(self):
        """True if quantity is non-zero and at or below min_quantity."""
        return self.min_quantity > 0 and self.quantity <= self.min_quantity

    @property
    def days_until_expiry(self):
        """Return days until expiry (negative if past), or None."""
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - datetime.now(timezone.utc)
        return delta.days

    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'quantity': self.quantity,
            'unit': self.unit,
            'category': self.category,
            'min_quantity': self.min_quantity,
            'is_low_stock': self.is_low_stock,
            'days_until_expiry': self.days_until_expiry,
            'purchased_date': self.purchased_date.isoformat() if self.purchased_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<PantryItem {self.name}>'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryItemModel -v 2>&1`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_pantry.py
git commit -m "feat: add PantryItem model with is_low_stock and days_until_expiry"
```

---

### Task 2: Pantry API Routes

**Files:**
- Modify: `app/routes.py` — add pantry API endpoints within the `api_bp` blueprint
- Test: `tests/test_pantry.py` — API endpoint tests

- [ ] **Step 1: Write the failing API tests**

Add the following class to `tests/test_pantry.py`:

```python
import json


class TestPantryAPI:
    """Tests for the Pantry API endpoints."""

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

    def test_create_pantry_item(self, client):
        """POST /api/pantry/items creates a new item."""
        resp = client.post('/api/pantry/items', json={
            'name': 'Flour',
            'quantity': 5.0,
            'unit': 'cups',
            'category': 'Pantry',
            'min_quantity': 1.0,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Flour'
        assert data['quantity'] == 5.0
        assert data['unit'] == 'cups'
        assert data['category'] == 'Pantry'
        assert data['is_low_stock'] is False

    def test_create_pantry_item_duplicate(self, client, db_session):
        """POST /api/pantry/items with duplicate name returns 409."""
        from app.models import PantryItem
        db_session.add(PantryItem(name="Tomato Sauce", quantity=2.0, unit="cans", category="Pantry"))
        db_session.commit()

        resp = client.post('/api/pantry/items', json={
            'name': 'Tomato Sauce',
            'quantity': 1.0,
            'unit': 'jar',
            'category': 'Pantry',
        })
        assert resp.status_code == 409
        assert 'already exists' in resp.get_json()['error']

    def test_create_pantry_item_missing_name(self, client):
        """POST /api/pantry/items without name returns 400."""
        resp = client.post('/api/pantry/items', json={'quantity': 2.0})
        assert resp.status_code == 400

    def test_update_pantry_item(self, client, db_session):
        """PUT /api/pantry/items/<id> updates an item."""
        from app.models import PantryItem
        item = PantryItem(name="Sugar", quantity=2.0, unit="cups", category="Pantry")
        db_session.add(item)
        db_session.commit()

        resp = client.put(f'/api/pantry/items/{item.id}', json={
            'quantity': 1.0,
            'notes': 'Almost out',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 1.0
        assert data['notes'] == 'Almost out'

    def test_update_pantry_item_not_found(self, client):
        """PUT /api/pantry/items/<id> for non-existent returns 404."""
        resp = client.put('/api/pantry/items/99999', json={'quantity': 1.0})
        assert resp.status_code == 404

    def test_delete_pantry_item(self, client, db_session):
        """DELETE /api/pantry/items/<id> removes an item."""
        from app.models import PantryItem
        item = PantryItem(name="Old Spice", quantity=1.0, unit="jar", category="Spices")
        db_session.add(item)
        db_session.commit()

        resp = client.delete(f'/api/pantry/items/{item.id}')
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = client.get('/api/pantry/items')
        assert len(resp2.get_json()) == 0

    def test_delete_pantry_item_not_found(self, client):
        """DELETE /api/pantry/items/<id> for non-existent returns 404."""
        resp = client.delete('/api/pantry/items/99999')
        assert resp.status_code == 404

    def test_deduct_quantity(self, client, db_session):
        """POST /api/pantry/items/<id>/deduct reduces quantity."""
        from app.models import PantryItem
        item = PantryItem(name="Flour", quantity=10.0, unit="cups", category="Pantry")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f'/api/pantry/items/{item.id}/deduct', json={'quantity': 3.0})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 7.0

    def test_deduct_quantity_negative_result(self, client, db_session):
        """POST /api/pantry/items/<id>/deduct cannot go below 0."""
        from app.models import PantryItem
        item = PantryItem(name="Eggs", quantity=2.0, unit="dozen", category="Dairy")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f'/api/pantry/items/{item.id}/deduct', json={'quantity': 5.0})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quantity'] == 0  # Clamped to 0

    def test_deduct_quantity_not_found(self, client):
        """POST /api/pantry/items/<id>/deduct for non-existent returns 404."""
        resp = client.post('/api/pantry/items/99999/deduct', json={'quantity': 1.0})
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

    def test_ingredients_to_pantry(self, client, db_session, app):
        """POST /api/pantry/ingredients-to-pantry imports recipe ingredients."""
        from app.models import Recipe
        recipe = Recipe(
            title="Test Pasta",
            instructions="Boil water.",
            ingredients="1 lb pasta\n2 cups tomato sauce\n1 tbsp olive oil",
        )
        db_session.add(recipe)
        db_session.commit()

        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': recipe.id})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['count'] == 3
        names = [item['name'] for item in data['items']]
        assert 'pasta' in names
        assert 'tomato sauce' in names
        assert 'olive oil' in names

    def test_ingredients_to_pantry_no_ingredients(self, client, db_session):
        """POST /api/pantry/ingredients-to-pantry on recipe without ingredients."""
        from app.models import Recipe
        recipe = Recipe(title="Empty", instructions="Do nothing.")
        db_session.add(recipe)
        db_session.commit()

        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': recipe.id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 0

    def test_ingredients_to_pantry_not_found(self, client):
        """POST /api/pantry/ingredients-to-pantry for non-existent recipe."""
        resp = client.post('/api/pantry/ingredients-to-pantry', json={'recipe_id': 99999})
        assert resp.status_code == 404

    def test_ingredients_to_pantry_no_recipe_id(self, client):
        """POST /api/pantry/ingredients-to-pantry without recipe_id returns 400."""
        resp = client.post('/api/pantry/ingredients-to-pantry', json={})
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryAPI -v 2>&1`
Expected: Most tests FAIL with 404 (no routes) or 405

- [ ] **Step 3: Implement API routes in routes.py**

Add the following as a new section in `app/routes.py` (after the Shopping List routes, before the Meal Plan routes), inside the `api_bp` blueprint:

```python

# ============================================================================
# Pantry API Routes
# ============================================================================

@api_bp.route('/pantry/items', methods=['GET'])
def list_pantry_items():
    """List all pantry items, optionally filtered by category.

    Query: ?category=X
    """
    category = request.args.get('category')
    query = PantryItem.query

    if category:
        query = query.filter(PantryItem.category == category)

    items = query.order_by(PantryItem.name.asc()).all()
    return jsonify([item.to_dict() for item in items])


@api_bp.route('/pantry/items', methods=['POST'])
@editor_or_admin
def create_pantry_item():
    """Create a new pantry item.

    Expects JSON: { name (required), quantity, unit, category, min_quantity,
                    purchased_date, expiry_date, notes }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Check for existing item (case-insensitive)
    existing = PantryItem.query.filter(
        db.func.lower(PantryItem.name) == db.func.lower(name)
    ).first()
    if existing:
        return jsonify({'error': f'Item "{name}" already exists'}), 409

    try:
        item = PantryItem(
            name=name,
            quantity=float(data.get('quantity', 0)),
            unit=data.get('unit'),
            category=data.get('category', 'Other'),
            min_quantity=float(data.get('min_quantity', 0)),
            notes=data.get('notes'),
        )

        # Parse dates if provided
        if 'purchased_date' in data and data['purchased_date']:
            try:
                item.purchased_date = datetime.fromisoformat(data['purchased_date'])
            except (ValueError, TypeError):
                pass
        if 'expiry_date' in data and data['expiry_date']:
            try:
                item.expiry_date = datetime.fromisoformat(data['expiry_date'])
            except (ValueError, TypeError):
                pass

        db.session.add(item)
        db.session.commit()
        return jsonify(item.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to create pantry item: {e}')
        return jsonify({'error': 'Failed to create item'}), 500


@api_bp.route('/pantry/items/<int:item_id>', methods=['PUT'])
@editor_or_admin
def update_pantry_item(item_id):
    """Update a pantry item.

    Expects JSON with any updatable fields.
    """
    item = db.get_or_404(PantryItem, item_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data and data['name'].strip():
        new_name = data['name'].strip()
        # Check for conflict with other items
        existing = PantryItem.query.filter(
            db.func.lower(PantryItem.name) == db.func.lower(new_name),
            PantryItem.id != item_id
        ).first()
        if existing:
            return jsonify({'error': f'Item "{new_name}" already exists'}), 409
        item.name = new_name

    if 'quantity' in data:
        item.quantity = float(data['quantity'])
    if 'unit' in data:
        item.unit = data['unit'] or None
    if 'category' in data:
        item.category = data['category']
    if 'min_quantity' in data:
        item.min_quantity = float(data['min_quantity'])
    if 'notes' in data:
        item.notes = data['notes'] or None
    if 'purchased_date' in data:
        try:
            item.purchased_date = datetime.fromisoformat(data['purchased_date']) if data['purchased_date'] else None
        except (ValueError, TypeError):
            pass
    if 'expiry_date' in data:
        try:
            item.expiry_date = datetime.fromisoformat(data['expiry_date']) if data['expiry_date'] else None
        except (ValueError, TypeError):
            pass

    db.session.commit()
    return jsonify(item.to_dict())


@api_bp.route('/pantry/items/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_pantry_item(item_id):
    """Delete a pantry item."""
    item = db.get_or_404(PantryItem, item_id)
    db.session.delete(item)
    db.session.commit()
    return '', 204


@api_bp.route('/pantry/items/<int:item_id>/deduct', methods=['POST'])
@editor_or_admin
def deduct_pantry_item(item_id):
    """Deduct a quantity from a pantry item (clamped to 0)."""
    item = db.get_or_404(PantryItem, item_id)
    data = request.get_json()
    if not data or 'quantity' not in data:
        return jsonify({'error': 'quantity is required'}), 400

    deduct_qty = float(data['quantity'])
    item.quantity = max(0, item.quantity - deduct_qty)
    db.session.commit()
    return jsonify(item.to_dict())


@api_bp.route('/pantry/low-stock', methods=['GET'])
def get_low_stock_items():
    """Return items where quantity <= min_quantity (and min_quantity > 0)."""
    items = PantryItem.query.filter(
        PantryItem.min_quantity > 0,
        PantryItem.quantity <= PantryItem.min_quantity
    ).order_by(PantryItem.name.asc()).all()
    return jsonify([item.to_dict() for item in items])


@api_bp.route('/pantry/ingredients-to-pantry', methods=['POST'])
@editor_or_admin
def import_ingredients_to_pantry():
    """Bulk import recipe ingredients as pantry items.

    Expects JSON: { recipe_id: N }
    Parses the recipe's ingredients text (one per line, optional quantity prefix)
    and creates/updates PantryItems.
    """
    data = request.get_json()
    if not data or 'recipe_id' not in data:
        return jsonify({'error': 'recipe_id is required'}), 400

    recipe = db.get_or_404(Recipe, data['recipe_id'])
    if not recipe.ingredients:
        return jsonify({'items': [], 'count': 0})

    added = []
    for line in recipe.ingredients.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # Try to extract item name from ingredient line
        # Remove leading quantity/unit (e.g. "1 lb", "2 cups", "1 tbsp")
        name = _parse_ingredient_name(line)
        if not name:
            continue

        item = _upsert_pantry_item_from_ingredient(name)
        if item:
            added.append(item.to_dict())

    db.session.commit()
    return jsonify({'items': added, 'count': len(added)}), 201 if added else 200
```

Also add the following helper functions near the top of `routes.py` (after the existing helpers, before main page routes):

```python

# Pantry helpers
def _parse_ingredient_name(ingredient_line):
    """Extract a clean item name from an ingredient line.

    Strips leading quantity/unit prefixes like '1 lb', '2 cups', '1 tbsp'.
    Returns the normalized name or None if line is empty.
    """
    # Basic heuristic: remove leading number and unit, take the rest
    import re
    # Match patterns like "1 lb", "2 cups", "1/2 cup", "1 tbsp", "2 tsp", etc.
    cleaned = re.sub(r'^[\d\s./]+\s*(lb|lbs|pound|pounds|oz|ounce|ounces|'
                     r'cup|cups|tbsp|tablespoon|tablespoons|tsp|teaspoon|teaspoons|'
                     r'g|gram|grams|kg|kilogram|kilograms|ml|milliliter|milliliters|'
                     r'l|liter|liters|clove|cloves|pinch|dash|can|cans|jar|jars|'
                     r'box|boxes|bottle|bottles|bag|bags|piece|pieces|slice|slices|'
                     r'head|heads|bunch|bunches|stalk|stalks|sprig|sprigs|'
                     r'package|packages|container|containers|packet|packets'
                     r')?\s+', '', ingredient_line, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip('.,;')
    return cleaned if cleaned else None


def _upsert_pantry_item_from_ingredient(name):
    """Find existing pantry item or create a new one for an ingredient name.

    Uses case-insensitive lookup. If found, increments quantity by 1.
    If not found, creates with quantity=1 and category='Other'.
    """
    normalized_name = name.strip().lower()

    existing = PantryItem.query.filter(
        db.func.lower(PantryItem.name) == normalized_name
    ).first()

    if existing:
        existing.quantity += 1.0
        return existing

    item = PantryItem(
        name=name.strip(),
        quantity=1.0,
        category='Other',
    )
    db.session.add(item)
    return item
```

And update the imports in `routes.py` to include the new model and helpers:

```python
# In the imports section, add PantryItem to the existing import:
from app.models import (Recipe, Tag, Note, ShoppingItem,
                         Store, StoreAisle, AisleOverride, MealPlan,
                         PrepSession, PrepSessionRecipe, PrepTask,
                         PantryItem,  # <-- ADD THIS
                         classify_aisle, seed_default_store)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryAPI -v 2>&1`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes.py tests/test_pantry.py
git commit -m "feat: add pantry API routes (CRUD, deduct, low-stock, bulk import)"
```

---

### Task 3: Pantry HTML Template (Web UI)

**Files:**
- Create: `app/templates/pantry.html`
- Modify: `app/routes.py` — add `GET /pantry` route in `main_bp`
- Modify: `app/templates/layout.html` — add pantry link in navigation

- [ ] **Step 1: Write the failing template test**

Add to `tests/test_pantry.py`:

```python
class TestPantryWeb:
    """Tests for the pantry web UI."""

    def test_pantry_page_loads(self, client):
        """GET /pantry returns 200."""
        resp = client.get('/pantry')
        assert resp.status_code == 200

    def test_pantry_page_content(self, client, db_session):
        """GET /pantry shows pantry items on the page."""
        from app.models import PantryItem
        item = PantryItem(name="Chicken", quantity=2.0, unit="lbs", category="Meat")
        db_session.add(item)
        db_session.commit()

        resp = client.get('/pantry')
        assert resp.status_code == 200
        # Check the page renders item data
        html = resp.data.decode()
        assert 'Chicken' in html
        assert '2.0' in html or '2' in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryWeb -v 2>&1`
Expected: FAIL with 404

- [ ] **Step 3: Add the GET /pantry route**

Add to `app/routes.py` in the `main_bp` section (after the features route):

```python
@main_bp.route('/pantry')
def pantry_page():
    """Render the pantry inventory page."""
    return render_template('pantry.html')
```

- [ ] **Step 4: Create the pantry.html template**

Create `app/templates/pantry.html`:

```html
{% extends "layout.html" %}

{% block title %}Pantry - Kitchen Companion{% endblock %}

{% block extra_css %}
<style>
    .category-section {
        border-left-width: 4px;
        border-left-style: solid;
    }
    .cat-color-0 { border-left-color: #3b82f6; }
    .cat-color-1 { border-left-color: #10b981; }
    .cat-color-2 { border-left-color: #f59e0b; }
    .cat-color-3 { border-left-color: #8b5cf6; }
    .cat-color-4 { border-left-color: #ef4444; }
    .cat-color-5 { border-left-color: #06b6d4; }
    .cat-color-6 { border-left-color: #f97316; }
    .cat-color-7 { border-left-color: #ec4899; }
    .cat-color-8 { border-left-color: #14b8a6; }
    .cat-color-9 { border-left-color: #6366f1; }
    .cat-color-10 { border-left-color: #84cc16; }
    .cat-color-11 { border-left-color: #a855f7; }
    .cat-color-12 { border-left-color: #78716c; }
    .cat-color-13 { border-left-color: #d946ef; }
    .cat-color-14 { border-left-color: #64748b; }

    .expiry-badge {
        font-size: 0.7rem;
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-weight: 600;
    }
    .expiry-ok { background-color: #d1fae5; color: #065f46; }
    .expiry-soon { background-color: #fef3c7; color: #92400e; }
    .expiry-expired { background-color: #fee2e2; color: #991b1b; }

    .low-stock-badge {
        background-color: #fee2e2;
        color: #dc2626;
        font-weight: 700;
        font-size: 0.65rem;
        padding: 0.15rem 0.4rem;
        border-radius: 0.25rem;
    }

    .pantry-modal-overlay {
        background: rgba(0, 0, 0, 0.4);
    }
</style>
{% endblock %}

{% block content %}
<div class="p-4 md:p-8 max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-4">
        <h1 class="text-2xl md:text-3xl font-bold text-gray-900 flex items-center">
            <span class="text-3xl mr-3">🧺</span>Pantry Inventory
        </h1>
        <div class="flex gap-2">
            <button id="import-recipe-btn"
                class="px-4 py-2 text-sm font-medium text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-xl transition-colors">
                📥 Import from Recipe
            </button>
            <button id="add-item-btn"
                class="px-4 py-2 text-sm font-medium bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors">
                + Add Item
            </button>
        </div>
    </div>

    <!-- Import from Recipe Panel (hidden) -->
    <div id="import-panel" class="hidden mb-4 bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
        <h3 class="text-sm font-semibold text-gray-700 mb-3">Import Ingredients from Recipe</h3>
        <div class="flex gap-2">
            <select id="recipe-select"
                class="flex-1 px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 text-base">
                <option value="">-- Select a recipe --</option>
            </select>
            <button id="import-btn"
                class="px-6 py-2 bg-primary-600 text-white font-medium rounded-xl hover:bg-primary-700 transition-colors">
                Import
            </button>
        </div>
        <div id="import-result" class="hidden mt-3 text-sm text-green-600"></div>
    </div>

    <!-- Low-Stock Alerts Section -->
    <div id="low-stock-section" class="hidden mb-4 bg-red-50 border border-red-200 rounded-2xl p-4">
        <h3 class="text-sm font-bold text-red-800 mb-2">⚠️ Low Stock Alerts</h3>
        <div id="low-stock-list" class="space-y-2"></div>
    </div>

    <!-- Filter / Category Tabs -->
    <div class="mb-4 flex flex-wrap gap-2">
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-primary-600 text-white" data-category="">
            All
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Produce">
            🥬 Produce
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Meat">
            🥩 Meat
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Dairy">
            🥛 Dairy
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Pantry">
            🥫 Pantry
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Spices">
            🌿 Spices
        </button>
        <button class="category-filter px-3 py-1.5 text-sm rounded-xl font-medium bg-gray-100 text-gray-600 hover:bg-gray-200" data-category="Other">
            📦 Other
        </button>
    </div>

    <!-- Items Grid (grouped by category) -->
    <div id="pantry-items" class="space-y-4">
        <!-- Populated dynamically -->
    </div>

    <!-- Empty State -->
    <div id="empty-state" class="hidden text-center py-16">
        <div class="text-6xl mb-4">🧺</div>
        <h2 class="text-xl font-semibold text-gray-700 mb-2">Your pantry is empty</h2>
        <p class="text-gray-400">Add items manually or import ingredients from a recipe</p>
    </div>
</div>

<!-- Add/Edit Modal -->
<div id="item-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 pantry-modal-overlay" onclick="closeItemModal()"></div>
    <div class="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div class="p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 id="modal-title" class="text-lg font-bold text-gray-900">Add Pantry Item</h3>
                <button onclick="closeItemModal()" class="p-2 text-gray-400 hover:text-gray-600 rounded-xl hover:bg-gray-100">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>

            <form id="item-form" class="space-y-4">
                <input type="hidden" id="edit-item-id">

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                    <input type="text" id="item-name"
                        class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                        required maxlength="255">
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                        <input type="number" id="item-quantity" step="0.1" min="0"
                            class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                            value="0">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Unit</label>
                        <input type="text" id="item-unit"
                            class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                            placeholder="cups, lbs, pieces..." maxlength="50">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Category</label>
                    <select id="item-category"
                        class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
                        <option value="Produce">🥬 Produce</option>
                        <option value="Meat">🥩 Meat</option>
                        <option value="Dairy">🥛 Dairy</option>
                        <option value="Pantry">🥫 Pantry</option>
                        <option value="Spices">🌿 Spices</option>
                        <option value="Frozen">❄️ Frozen</option>
                        <option value="Beverages">☕ Beverages</option>
                        <option value="Other">📦 Other</option>
                    </select>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Low Stock Threshold</label>
                    <input type="number" id="item-min-qty" step="0.1" min="0"
                        class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                        value="0" placeholder="0 = no alert">
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Purchase Date</label>
                        <input type="date" id="item-purchased-date"
                            class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Expiry Date</label>
                        <input type="date" id="item-expiry-date"
                            class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                    <textarea id="item-notes"
                        class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
                        rows="2" maxlength="2000"></textarea>
                </div>

                <div class="flex gap-3 pt-2">
                    <button type="submit"
                        class="flex-1 px-4 py-3 bg-primary-600 text-white font-semibold rounded-xl hover:bg-primary-700 transition-colors">
                        Save
                    </button>
                    <button type="button" onclick="closeItemModal()"
                        class="px-4 py-3 text-gray-500 font-medium rounded-xl hover:bg-gray-100 transition-colors">
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
    let state = {
        items: [],
        currentCategory: '',
        recipes: []
    };

    const CATEGORY_EMOJIS = {
        'Produce': '🥬', 'Meat': '🥩', 'Dairy': '🥛',
        'Pantry': '🥫', 'Spices': '🌿', 'Frozen': '❄️',
        'Beverages': '☕', 'Other': '📦'
    };

    function getColorClass(category, idx) {
        // Use a stable color based on category name or index
        const catIndex = ['Produce', 'Meat', 'Dairy', 'Pantry', 'Spices', 'Frozen', 'Beverages', 'Other'].indexOf(category);
        return `cat-color-${catIndex >= 0 ? catIndex : 14}`;
    }

    // ── Data loading ──────────────────────────────────────────────────

    async function loadItems(category) {
        let url = '/api/pantry/items';
        if (category) url += `?category=${encodeURIComponent(category)}`;
        try {
            const resp = await fetch(url);
            state.items = await resp.json();
            renderItems();
        } catch (e) {
            console.error('Failed to load pantry items:', e);
        }
    }

    async function loadRecipes() {
        try {
            const resp = await fetch('/recipes/simple');
            state.recipes = await resp.json();
            const select = document.getElementById('recipe-select');
            // Keep the placeholder
            select.innerHTML = '<option value="">-- Select a recipe --</option>' +
                state.recipes.map(r => `<option value="${r.id}">${escapeHtml(r.title)}</option>`).join('');
        } catch (e) {
            console.error('Failed to load recipes:', e);
        }
    }

    async function loadLowStock() {
        try {
            const resp = await fetch('/api/pantry/low-stock');
            const items = await resp.json();
            const section = document.getElementById('low-stock-section');
            const list = document.getElementById('low-stock-list');

            if (items.length === 0) {
                section.classList.add('hidden');
                return;
            }

            section.classList.remove('hidden');
            list.innerHTML = items.map(item => `
                <div class="flex items-center justify-between bg-white rounded-xl px-3 py-2 border border-red-100">
                    <div>
                        <span class="font-medium text-gray-900">${escapeHtml(item.name)}</span>
                        <span class="text-sm text-gray-500 ml-2">${item.quantity} ${item.unit || ''} (min: ${item.min_quantity})</span>
                    </div>
                    <button onclick="addToShoppingList('${escapeHtml(item.name)}')"
                        class="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors">
                        + Shopping List
                    </button>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load low stock:', e);
        }
    }

    // ── Rendering ─────────────────────────────────────────────────────

    function renderItems() {
        const container = document.getElementById('pantry-items');
        const emptyState = document.getElementById('empty-state');

        if (state.items.length === 0) {
            container.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');

        // Group by category (preserving a stable order)
        const categories = ['Produce', 'Meat', 'Dairy', 'Pantry', 'Spices', 'Frozen', 'Beverages', 'Other'];
        const grouped = {};
        state.items.forEach(item => {
            const cat = item.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(item);
        });

        container.innerHTML = categories.map(cat => {
            if (!grouped[cat] || grouped[cat].length === 0) return '';
            const colorClass = getColorClass(cat);
            const itemsHtml = grouped[cat].map(item => renderItemCard(item)).join('');
            const emoji = CATEGORY_EMOJIS[cat] || '📦';
            return `
                <div class="category-section ${colorClass} bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                    <div class="px-4 py-3 bg-gray-50 border-b border-gray-100 font-semibold text-gray-700 text-sm flex items-center justify-between">
                        <span>${emoji} ${cat} <span class="text-gray-400 font-normal">(${grouped[cat].length})</span></span>
                    </div>
                    <div class="divide-y divide-gray-100">
                        ${itemsHtml}
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderItemCard(item) {
        const lowStock = item.is_low_stock ? '<span class="low-stock-badge ml-2">LOW</span>' : '';
        const unit = item.unit ? ` ${escapeHtml(item.unit)}` : '';

        let expiryBadge = '';
        if (item.days_until_expiry !== null) {
            if (item.days_until_expiry < 0) {
                expiryBadge = `<span class="expiry-badge expiry-expired">Expired</span>`;
            } else if (item.days_until_expiry <= 7) {
                expiryBadge = `<span class="expiry-badge expiry-soon">${item.days_until_expiry}d</span>`;
            } else {
                expiryBadge = `<span class="expiry-badge expiry-ok">${item.days_until_expiry}d</span>`;
            }
        }

        const notes = item.notes ? `<p class="text-xs text-gray-400 mt-1">${escapeHtml(item.notes)}</p>` : '';

        return `
            <div class="px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center">
                        <span class="font-medium text-gray-900">${escapeHtml(item.name)}</span>
                        ${lowStock}
                        ${expiryBadge}
                    </div>
                    <div class="text-sm text-gray-500">
                        <span class="font-semibold">${item.quantity}</span>${unit}
                    </div>
                    ${notes}
                </div>
                <div class="flex gap-1 ml-2">
                    <button onclick="openEditModal(${item.id})"
                        class="px-2 py-1 text-xs text-gray-400 hover:text-primary-600 rounded-lg hover:bg-primary-50"
                        title="Edit">✏️</button>
                    <button onclick="deductItem(${item.id})"
                        class="px-2 py-1 text-xs text-gray-400 hover:text-orange-600 rounded-lg hover:bg-orange-50"
                        title="Deduct">➖</button>
                    <button onclick="deleteItem(${item.id})"
                        class="px-2 py-1 text-xs text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                        title="Delete">🗑️</button>
                </div>
            </div>
        `;
    }

    // ── Add to Shopping List ─────────────────────────────────────────

    async function addToShoppingList(name) {
        try {
            const resp = await fetch('/shopping-items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: [{ name }] })
            });
            if (resp.ok) {
                // Flash a success somehow — simple alert for now
                // Re-render isn't needed since shopping list is separate page
                alert(`"${name}" added to shopping list`);
            } else {
                const data = await resp.json();
                if (data.error) alert(data.error);
            }
        } catch (e) {
            console.error('Failed to add to shopping list:', e);
        }
    }

    // ── Modal operations ──────────────────────────────────────────────

    function openAddModal() {
        document.getElementById('modal-title').textContent = 'Add Pantry Item';
        document.getElementById('edit-item-id').value = '';
        document.getElementById('item-form').reset();
        document.getElementById('item-quantity').value = '0';
        document.getElementById('item-min-qty').value = '0';
        document.getElementById('item-category').value = 'Produce';
        document.getElementById('item-modal').classList.remove('hidden');
    }

    async function openEditModal(itemId) {
        const item = state.items.find(i => i.id === itemId);
        if (!item) return;

        document.getElementById('modal-title').textContent = 'Edit Pantry Item';
        document.getElementById('edit-item-id').value = item.id;
        document.getElementById('item-name').value = item.name;
        document.getElementById('item-quantity').value = item.quantity;
        document.getElementById('item-unit').value = item.unit || '';
        document.getElementById('item-category').value = item.category || 'Other';
        document.getElementById('item-min-qty').value = item.min_quantity;
        document.getElementById('item-notes').value = item.notes || '';

        if (item.purchased_date) {
            document.getElementById('item-purchased-date').value = item.purchased_date.slice(0, 10);
        } else {
            document.getElementById('item-purchased-date').value = '';
        }
        if (item.expiry_date) {
            document.getElementById('item-expiry-date').value = item.expiry_date.slice(0, 10);
        } else {
            document.getElementById('item-expiry-date').value = '';
        }

        document.getElementById('item-modal').classList.remove('hidden');
    }

    function closeItemModal() {
        document.getElementById('item-modal').classList.add('hidden');
    }

    // ── CRUD actions ──────────────────────────────────────────────────

    document.getElementById('item-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const editId = document.getElementById('edit-item-id').value;
        const name = document.getElementById('item-name').value.trim();
        if (!name) return;

        const body = {
            name,
            quantity: parseFloat(document.getElementById('item-quantity').value) || 0,
            unit: document.getElementById('item-unit').value.trim() || null,
            category: document.getElementById('item-category').value,
            min_quantity: parseFloat(document.getElementById('item-min-qty').value) || 0,
            notes: document.getElementById('item-notes').value.trim() || null,
        };

        const purchasedDate = document.getElementById('item-purchased-date').value;
        const expiryDate = document.getElementById('item-expiry-date').value;
        if (purchasedDate) body.purchased_date = purchasedDate + 'T00:00:00';
        if (expiryDate) body.expiry_date = expiryDate + 'T00:00:00';

        try {
            let resp;
            if (editId) {
                resp = await fetch(`/api/pantry/items/${editId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            } else {
                resp = await fetch('/api/pantry/items', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            }

            if (!resp.ok) {
                const data = await resp.json();
                alert(data.error || 'Failed to save item');
                return;
            }

            closeItemModal();
            await loadItems(state.currentCategory);
            await loadLowStock();
        } catch (e) {
            console.error('Failed to save item:', e);
            alert('Failed to save item');
        }
    });

    async function deductItem(itemId) {
        const qty = prompt('How much to deduct?', '1');
        if (qty === null) return;
        const num = parseFloat(qty);
        if (isNaN(num) || num <= 0) return;

        try {
            const resp = await fetch(`/api/pantry/items/${itemId}/deduct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ quantity: num }),
            });
            if (resp.ok) {
                await loadItems(state.currentCategory);
                await loadLowStock();
            }
        } catch (e) {
            console.error('Failed to deduct:', e);
        }
    }

    async function deleteItem(itemId) {
        if (!confirm('Remove this item from pantry?')) return;
        try {
            const resp = await fetch(`/api/pantry/items/${itemId}`, { method: 'DELETE' });
            if (resp.ok || resp.status === 204) {
                await loadItems(state.currentCategory);
                await loadLowStock();
            }
        } catch (e) {
            console.error('Failed to delete:', e);
        }
    }

    // ── Category filter ───────────────────────────────────────────────

    document.querySelectorAll('.category-filter').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.category-filter').forEach(b => {
                b.classList.remove('bg-primary-600', 'text-white');
                b.classList.add('bg-gray-100', 'text-gray-600');
            });
            this.classList.remove('bg-gray-100', 'text-gray-600');
            this.classList.add('bg-primary-600', 'text-white');

            state.currentCategory = this.dataset.category;
            loadItems(state.currentCategory);
        });
    });

    // ── Import from Recipe ────────────────────────────────────────────

    document.getElementById('import-recipe-btn').addEventListener('click', () => {
        const panel = document.getElementById('import-panel');
        panel.classList.toggle('hidden');
        if (!panel.classList.contains('hidden')) {
            loadRecipes();
        }
    });

    document.getElementById('import-btn').addEventListener('click', async () => {
        const recipeId = document.getElementById('recipe-select').value;
        if (!recipeId) return;

        try {
            const resp = await fetch('/api/pantry/ingredients-to-pantry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recipe_id: parseInt(recipeId) }),
            });
            const data = await resp.json();
            const result = document.getElementById('import-result');
            result.classList.remove('hidden');
            result.textContent = `✓ Imported ${data.count} item${data.count !== 1 ? 's' : ''}`;
            await loadItems(state.currentCategory);
            await loadLowStock();
        } catch (e) {
            console.error('Failed to import:', e);
            alert('Failed to import ingredients');
        }
    });

    // ── Keyboard shortcuts ────────────────────────────────────────────

    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('item-modal');
        if (modal.classList.contains('hidden')) return;
        if (e.key === 'Escape') closeItemModal();
    });

    // ── Init ──────────────────────────────────────────────────────────

    document.getElementById('add-item-btn').addEventListener('click', openAddModal);

    async function init() {
        await loadItems('');
        await loadLowStock();
    }

    document.addEventListener('DOMContentLoaded', init);
</script>
{% endblock %}
```

- [ ] **Step 5: Add pantry link to navigation in layout.html**

Read the layout.html first to find the navigation section, then add a pantry link.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/test_pantry.py::TestPantryWeb -v 2>&1`
Expected: All tests PASS

- [ ] **Step 7: Run all tests to check for regressions**

Run: `cd <worktree> && source venv/bin/activate && python -m pytest tests/ -v 2>&1 | tail -20`
Expected: All 375+ tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/templates/pantry.html app/routes.py app/templates/layout.html
git commit -m "feat: add pantry web UI with stock view, low-stock alerts, and recipe import"
```
