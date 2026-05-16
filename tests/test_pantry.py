"""Tests for PantryItem model and pantry API."""
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
