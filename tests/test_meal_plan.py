"""Tests for meal plan CRUD, week navigation, and edge cases."""
import pytest
import json
from datetime import date, timedelta
from app.models import Recipe, MealPlan
from app import db
from app.auth import User


# ── Helpers ──────────────────────────────────────────────────────────────

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


# ── CRUD ─────────────────────────────────────────────────────────────────

def test_get_meal_plan_empty_returns_week_range(client):
    """GET /meal-plan without existing data returns empty plan with correct week range."""
    resp = client.get('/meal-plan/data')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'plan_by_date' in data
    assert 'start_date' in data
    assert 'end_date' in data
    assert 'this_week' in data
    assert 'next_week' in data
    assert 'prev_week' in data

    # All 7 dates should be present
    days = list(data['plan_by_date'].keys())
    assert len(days) == 7

    # Every date should have an empty dict (no meals planned yet)
    for day in days:
        assert data['plan_by_date'][day] == {}


def test_create_meal_slot(auth_client, app):
    """POST /meal-plan creates a meal slot."""
    recipe_id = _make_recipe(app)
    today = date.today().isoformat()

    resp = auth_client.post('/meal-plan',
                            json={
                                'date': today,
                                'meal_type': 'dinner',
                                'recipe_id': recipe_id
                            })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['date'] == today
    assert data['meal_type'] == 'dinner'
    assert data['recipe_id'] == recipe_id


def test_get_meal_plan_returns_created_slot(auth_client, client, app):
    """GET /meal-plan returns created slot grouped under correct date/meal_type."""
    recipe_id = _make_recipe(app)
    # Use a Monday to make date calculations predictable
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    test_date = monday.isoformat()

    auth_client.post('/meal-plan',
                     json={
                         'date': test_date,
                         'meal_type': 'dinner',
                         'recipe_id': recipe_id
                     })

    resp = client.get('/meal-plan/data')
    data = json.loads(resp.data)

    assert test_date in data['plan_by_date']
    day_data = data['plan_by_date'][test_date]
    assert 'dinner' in day_data
    assert day_data['dinner']['recipe_id'] == recipe_id


def test_upsert_same_date_meal_type_updates(auth_client, app):
    """POST /meal-plan twice for same date+meal_type updates (upsert)."""
    recipe_1 = _make_recipe(app, "Pasta")
    recipe_2 = _make_recipe(app, "Salad")
    test_date = date.today().isoformat()

    # Create initial slot
    auth_client.post('/meal-plan',
                     json={
                         'date': test_date,
                         'meal_type': 'lunch',
                         'recipe_id': recipe_1
                     })

    # Upsert with different recipe
    resp = auth_client.post('/meal-plan',
                            json={
                                'date': test_date,
                                'meal_type': 'lunch',
                                'recipe_id': recipe_2
                            })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['recipe_id'] == recipe_2

    # Verify only one entry exists for this date+meal_type
    with app.app_context():
        count = MealPlan.query.filter_by(
            date=date.fromisoformat(test_date),
            meal_type='lunch'
        ).count()
        assert count == 1


def test_meal_plan_ignores_dates_outside_week(auth_client, client, app):
    """GET /meal-plan ignores dates outside requested week."""
    # Create a meal plan for a date far outside the current week
    far_future = (date.today() + timedelta(weeks=10)).isoformat()
    auth_client.post('/meal-plan',
                     json={
                         'date': far_future,
                         'meal_type': 'dinner',
                         'recipe_id': _make_recipe(app)
                     })

    resp = client.get('/meal-plan/data')
    data = json.loads(resp.data)
    # Check that far_future is NOT in the current week's response
    for day in data['plan_by_date']:
        day_data = data['plan_by_date'][day]
        assert 'dinner' not in day_data, \
            f"Meal from {far_future} leaked into week {data['this_week']}"


def test_delete_meal_plan_slot(auth_client, client, app):
    """DELETE /meal-plan/<id> removes the slot."""
    recipe_id = _make_recipe(app)
    test_date = date.today().isoformat()

    r = auth_client.post('/meal-plan',
                         json={
                             'date': test_date,
                             'meal_type': 'dinner',
                             'recipe_id': recipe_id
                         })
    mp_id = json.loads(r.data)['id']

    resp = auth_client.delete(f'/meal-plan/{mp_id}')
    assert resp.status_code == 204

    # Verify it's gone from the plan
    resp2 = client.get('/meal-plan/data')
    data = json.loads(resp2.data)
    day_data = data['plan_by_date'].get(test_date, {})
    assert 'dinner' not in day_data


def test_create_notes_only_slot(auth_client, app):
    """POST /meal-plan without recipe_id creates a notes-only slot."""
    test_date = date.today().isoformat()

    resp = auth_client.post('/meal-plan',
                            json={
                                'date': test_date,
                                'meal_type': 'breakfast',
                                'notes': 'Just cereal today'
                            })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['recipe_id'] is None
    assert data['notes'] == 'Just cereal today'
    assert data['date'] == test_date
    assert data['meal_type'] == 'breakfast'


# ── Week Navigation ──────────────────────────────────────────────────────

def test_default_week_is_current_iso_week(client):
    """Default week param returns current ISO week."""
    resp = client.get('/meal-plan/data')
    data = json.loads(resp.data)

    today = date.today()
    iso = today.isocalendar()
    expected_week = f'{iso[0]}-W{iso[1]:02d}'
    assert data['this_week'] == expected_week


def test_explicit_week_returns_correct_range(client):
    """?week=2026-W20 returns correct date range (May 11-17, 2026 per ISO 8601)."""
    resp = client.get('/meal-plan/data?week=2026-W20')
    data = json.loads(resp.data)

    # ISO week 20 in 2026: Jan 1 is Thursday → week 1 is Dec 29-Jan 4
    # Week 20 = May 11-17
    assert data['start_date'] == '2026-05-11'
    assert data['end_date'] == '2026-05-17'

    days = list(data['plan_by_date'].keys())
    assert days[0] == '2026-05-11'
    assert days[-1] == '2026-05-17'


def test_navigation_links_are_correct(client):
    """next_week and prev_week navigation links are correct."""
    resp = client.get('/meal-plan/data?week=2026-W20')
    data = json.loads(resp.data)

    assert data['prev_week'] == '2026-W19'
    assert data['next_week'] == '2026-W21'
    assert data['this_week'] == '2026-W20'


def test_year_boundary_prev_week(client):
    """prev_week of 2026-W01 is 2025-W52."""
    resp = client.get('/meal-plan/data?week=2026-W01')
    data = json.loads(resp.data)
    assert data['prev_week'] == '2025-W52'


def test_year_boundary_next_week(client):
    """next_week of 2026-W53 is 2027-W01 (2026 has 53 ISO weeks)."""
    resp = client.get('/meal-plan/data?week=2026-W53')
    data = json.loads(resp.data)
    assert data['next_week'] == '2027-W01'


# ── Recipe Lookup ────────────────────────────────────────────────────────

def test_recipes_simple_returns_id_and_title_only(client, app):
    """GET /recipes/simple returns recipes with only id and title."""
    _make_recipe(app, "Spaghetti Carbonara")
    _make_recipe(app, "Caesar Salad")

    resp = client.get('/recipes/simple')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data) >= 2

    for recipe in data:
        assert 'id' in recipe
        assert 'title' in recipe
        # Should NOT have full recipe details
        assert 'instructions' not in recipe
        assert 'ingredients' not in recipe
        assert 'cooking_time' not in recipe


def test_meal_slot_includes_recipe_title(auth_client, client, app):
    """Meal slot with recipe_id includes recipe_title in response."""
    recipe_id = _make_recipe(app, "Chicken Tikka Masala")
    test_date = date.today().isoformat()

    auth_client.post('/meal-plan',
                     json={
                         'date': test_date,
                         'meal_type': 'dinner',
                         'recipe_id': recipe_id
                     })

    resp = client.get('/meal-plan/data')
    data = json.loads(resp.data)
    day_data = data['plan_by_date'].get(test_date, {})
    assert 'dinner' in day_data
    assert day_data['dinner']['recipe_title'] == 'Chicken Tikka Masala'


# ── Edge Cases ───────────────────────────────────────────────────────────

def test_invalid_week_format_uses_current_dates(client):
    """Invalid week format: date range falls back to current week."""
    resp = client.get('/meal-plan/data?week=not-a-week')
    assert resp.status_code == 200
    data = json.loads(resp.data)

    # start_date and end_date should be the current ISO week range
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    expected_start = monday.isoformat()
    expected_end = (monday + timedelta(days=6)).isoformat()

    assert data['start_date'] == expected_start
    assert data['end_date'] == expected_end


def test_meal_plan_recipe_title_null_when_recipe_missing(auth_client, app):
    """Meal plan shows recipe title null when recipe_id is null."""
    test_date = date.today().isoformat()

    r = auth_client.post('/meal-plan',
                         json={
                             'date': test_date,
                             'meal_type': 'snack',
                             'notes': 'Leftovers'
                         })
    data = json.loads(r.data)
    assert data['recipe_id'] is None
    assert data['recipe_title'] is None


def test_create_meal_plan_invalid_meal_type(auth_client, app):
    """POST /meal-plan with invalid meal_type returns 400."""
    resp = auth_client.post('/meal-plan',
                            json={
                                'date': date.today().isoformat(),
                                'meal_type': 'brunch',
                                'recipe_id': None
                            })
    assert resp.status_code == 400


def test_create_meal_plan_invalid_date(auth_client, app):
    """POST /meal-plan with invalid date format returns 400."""
    resp = auth_client.post('/meal-plan',
                            json={
                                'date': 'not-a-date',
                                'meal_type': 'dinner',
                            })
    assert resp.status_code == 400
