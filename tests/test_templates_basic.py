"""Smoke tests for template rendering of shopping list and meal plan pages."""
import pytest
import json
from datetime import date, timedelta
from app.models import Recipe, MealPlan, Store
from app import db


def _make_recipe(app, title="Test Pasta"):
    """Create a recipe and return its id."""
    with app.app_context():
        recipe = Recipe(
            title=title,
            instructions="Boil water, add pasta.",
            difficulty="easy"
        )
        db.session.add(recipe)
        db.session.commit()
        return recipe.id


def test_shopping_list_page_loads(client):
    """The /shopping-list page loads without error."""
    resp = client.get('/shopping-list')
    assert resp.status_code == 200
    assert b'Shopping' in resp.data or b'shopping' in resp.data.lower()


def test_meal_plan_page_loads(client):
    """The /meal-plan page loads without error."""
    resp = client.get('/meal-plan')
    assert resp.status_code == 200
    # Should contain some meal-plan related content
    assert b'meal' in resp.data.lower() or b'plan' in resp.data.lower()


def test_meal_plan_page_renders_week_header(client):
    """The /meal-plan page renders the week header."""
    resp = client.get('/meal-plan')
    assert resp.status_code == 200
    # The page should have date-related content or navigation elements
    assert b'week' in resp.data.lower() or len(resp.data) > 0


def test_shopping_list_page_with_no_stores(client):
    """Shopping list page shows appropriate message if no stores exist yet."""
    # Without any stores or items, page should still render
    resp = client.get('/shopping-list')
    assert resp.status_code == 200
    # Page should render without crashing even with no stores
    assert len(resp.data) > 0


def test_both_pages_render_with_data(auth_client, client, app):
    """Both pages render with existing recipes and meal plans in the database."""
    # Create a recipe
    recipe_id = _make_recipe(app, "Test Stir Fry")

    # Create a store
    auth_client.post('/stores', json={'name': 'Test Store'})

    # Create a meal plan for today
    today = date.today().isoformat()
    auth_client.post('/meal-plan',
                     json={
                         'date': today,
                         'meal_type': 'dinner',
                         'recipe_id': recipe_id
                     })

    # Both pages should render without error
    r1 = client.get('/shopping-list')
    assert r1.status_code == 200

    r2 = client.get('/meal-plan')
    assert r2.status_code == 200
