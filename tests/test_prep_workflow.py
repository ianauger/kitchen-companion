"""Tests for the Master Prep Workflow feature (#58)."""
import pytest
import json
from app.models import PrepSession, PrepSessionRecipe, PrepTask, Recipe
from app.auth import User
from app import db


@pytest.fixture
def admin(app):
    """Create admin user and login."""
    with app.app_context():
        u = User(username='preptest', role='admin')
        u.set_password('Test1234!')
        db.session.add(u)
        db.session.commit()
    return {'username': 'preptest', 'password': 'Test1234!'}


@pytest.fixture
def auth_c(client, admin):
    client.post('/api/auth/signin', data=admin)
    return client


@pytest.fixture
def recipe_ids(app, auth_c):
    with app.app_context():
        r1 = Recipe(
            title='Pasta Primavera',
            ingredients='2 cups pasta\n1 cup broccoli\n3 cloves garlic',
            instructions='Cook pasta.\nChop garlic.\nSaute.\nToss.\nServe.',
            cooking_time=25, prep_time=10, difficulty='easy', servings=4
        )
        r2 = Recipe(
            title='Garlic Chicken',
            ingredients='2 chicken breasts\n4 cloves garlic\n1 tbsp oil',
            instructions='Season chicken.\nSear.\nRoast 20 min.\nRest.',
            cooking_time=30, prep_time=15, difficulty='medium', servings=2
        )
        db.session.add_all([r1, r2])
        db.session.commit()
        return [r1.id, r2.id]


class TestPrepSessions:
    def test_create(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Sunday Dinner', 'recipe_ids': recipe_ids
        })
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert len(data['recipes']) == 2

    def test_update(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Test', 'recipe_ids': [recipe_ids[0]]
        })
        sid = json.loads(resp.data)['id']
        resp = auth_c.put(f'/prep/sessions/{sid}', json={
            'name': 'Updated', 'recipe_ids': recipe_ids
        })
        assert resp.status_code == 200
        assert len(json.loads(resp.data)['recipes']) == 2

    def test_invalid(self, auth_c):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Bad', 'recipe_ids': [99999]
        })
        assert resp.status_code == 400


class TestPrepAnalysis:
    def test_analyze(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Analysis', 'recipe_ids': recipe_ids
        })
        sid = json.loads(resp.data)['id']
        resp = auth_c.post(f'/prep/sessions/{sid}/analyze')
        assert resp.status_code == 200
        assert len(json.loads(resp.data)['tasks']) > 0

    def test_toggle(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Toggle', 'recipe_ids': recipe_ids
        })
        sid = json.loads(resp.data)['id']
        resp = auth_c.post(f'/prep/sessions/{sid}/analyze')
        tid = json.loads(resp.data)['tasks'][0]['id']
        resp = auth_c.put(f'/prep/tasks/{tid}', json={'completed': True})
        assert resp.status_code == 200
        assert json.loads(resp.data)['completed'] is True

    def test_detail(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Detail', 'recipe_ids': recipe_ids
        })
        sid = json.loads(resp.data)['id']
        resp = auth_c.get(f'/prep/sessions/{sid}')
        assert resp.status_code == 200

    def test_ingredients(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Ingredients', 'recipe_ids': recipe_ids
        })
        sid = json.loads(resp.data)['id']
        resp = auth_c.get(f'/prep/sessions/{sid}/ingredients')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'garlic' in str(data)

    def test_timeline(self, auth_c, recipe_ids):
        resp = auth_c.post('/prep/sessions', json={
            'name': 'Timeline', 'recipe_ids': recipe_ids
        })
        sid = json.loads(resp.data)['id']
        auth_c.post(f'/prep/sessions/{sid}/analyze')
        resp = auth_c.get(f'/prep/sessions/{sid}/timeline')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['tasks']) > 0


class TestAnalyzerUnit:
    def test_shared(self, app):
        with app.app_context():
            r1 = Recipe(title='R1', ingredients='3 cloves garlic\n2 cups pasta',
                        instructions='Cook.\nServe.', difficulty='easy')
            r2 = Recipe(title='R2', ingredients='4 cloves garlic\n1 tbsp oil',
                        instructions='Cook.\nServe.', difficulty='easy')
            db.session.add_all([r1, r2])
            db.session.commit()
            from app.prep_analyzer import PrepAnalyzer
            shared = PrepAnalyzer([r1, r2]).detect_shared_ingredients()
            assert 'garlic' in shared

    def test_extract(self):
        from app.prep_analyzer import _extract_core_ingredient
        assert 'flour' in _extract_core_ingredient('2 cups all-purpose flour')
        assert 'garlic' in _extract_core_ingredient('3 cloves garlic, minced')

    def test_categorize(self):
        from app.prep_analyzer import _categorize_ingredient
        assert _categorize_ingredient('chicken') == 'Meat'
        assert _categorize_ingredient('broccoli') == 'Produce'

    def test_timeline_gen(self, app):
        with app.app_context():
            r = Recipe(title='R', ingredients='pasta', difficulty='easy',
                       instructions='Chop.\nCook 10 min.\nServe.')
            db.session.add(r)
            db.session.commit()
            from app.prep_analyzer import PrepAnalyzer
            tl = PrepAnalyzer([r]).generate_timeline()
            assert len(tl['tasks']) > 0
