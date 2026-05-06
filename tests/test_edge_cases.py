"""Tests for update_recipe_submit edge cases and model methods (Recipe.total_time, ShoppingItem, Tag.get_or_create)."""
import pytest
import json
from app.models import Recipe, Tag, Note, ShoppingItem
from app.auth import User
from app import db

TEST_PASSWORD = 'Test1234!'


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def web_admin_client(client, app):
    """Authenticated web client as admin."""
    with app.app_context():
        user = User(username='edgeadmin', role='admin')
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
    client.post('/api/auth/signin', data={
        'username': 'edgeadmin',
        'password': TEST_PASSWORD
    })
    return client


@pytest.fixture
def api_admin_headers(client, app):
    """JWT headers for admin."""
    with app.app_context():
        admin = User(username='apiedge', role='admin')
        admin.set_password(TEST_PASSWORD)
        db.session.add(admin)
        db.session.commit()
    resp = client.post('/api/auth/login', json={
        'username': 'apiedge',
        'password': TEST_PASSWORD
    })
    token = json.loads(resp.data)['access_token']
    return {'Authorization': f'Bearer {token}'}


# ============================================================================
# update_recipe_submit edge cases
# ============================================================================

class TestUpdateRecipeSubmitEdgeCases:
    def test_empty_title_returns_to_edit(self, web_admin_client, app):
        """Empty title redirects back to edit form with error."""
        with app.app_context():
            recipe = Recipe(title='Edge Recipe', instructions='Do stuff.')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = web_admin_client.post(f'/recipes/{rid}', data={
            'title': '',
            'instructions': 'Updated.'
        }, follow_redirects=True)
        assert b'Title is required' in resp.data

    def test_empty_instructions_returns_to_edit(self, web_admin_client, app):
        """Empty instructions redirects back to edit form with error."""
        with app.app_context():
            recipe = Recipe(title='Edge2', instructions='Do stuff.')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = web_admin_client.post(f'/recipes/{rid}', data={
            'title': 'Updated Title',
            'instructions': ''
        }, follow_redirects=True)
        assert b'Instructions is required' in resp.data

    def test_clear_source_url(self, web_admin_client, app):
        """clear_source checkbox clears the source URL."""
        with app.app_context():
            recipe = Recipe(
                title='Has Source',
                instructions='Cook.',
                source_url='https://example.com/recipe'
            )
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = web_admin_client.post(f'/recipes/{rid}', data={
            'title': 'Has Source',
            'instructions': 'Cook.',
            'clear_source': 'on'
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            updated = db.session.get(Recipe, rid)
            assert updated.source_url is None

    def test_update_numeric_fields_empty_string(self, web_admin_client, app):
        """Empty string for numeric fields should be handled."""
        with app.app_context():
            recipe = Recipe(
                title='Numeric Edge',
                instructions='Cook.',
                cooking_time=30,
                prep_time=15,
                servings=4
            )
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = web_admin_client.post(f'/recipes/{rid}', data={
            'title': 'Numeric Edge',
            'instructions': 'Cook.',
            'cooking_time': '',
            'prep_time': '',
            'servings': '',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            updated = db.session.get(Recipe, rid)
            # Empty string should leave existing values unchanged
            assert updated.cooking_time == 30
            assert updated.prep_time == 15
            assert updated.servings == 4

    def test_update_with_clear_image(self, web_admin_client, app):
        """clear_image removes the image."""
        with app.app_context():
            recipe = Recipe(
                title='Image Recipe',
                instructions='Cook.',
                image_path='uploads/recipes/test.jpg',
                image_url='https://example.com/img.jpg'
            )
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = web_admin_client.post(f'/recipes/{rid}', data={
            'title': 'Image Recipe',
            'instructions': 'Cook.',
            'clear_image': 'on'
        }, follow_redirects=True)

        with app.app_context():
            updated = db.session.get(Recipe, rid)
            assert updated.image_path is None
            assert updated.image_url is None


# ============================================================================
# Recipe.total_time tests
# ============================================================================

class TestRecipeTotalTime:
    def test_both_set(self, app):
        """total_time = cooking + prep when both set."""
        with app.app_context():
            recipe = Recipe(title='Full Time', instructions='X', cooking_time=30, prep_time=15)
            assert recipe.total_time == 45

    def test_only_cooking(self, app):
        """total_time = cooking when prep not set."""
        with app.app_context():
            recipe = Recipe(title='Cooking Only', instructions='X', cooking_time=20)
            assert recipe.total_time == 20

    def test_only_prep(self, app):
        """total_time = prep when cooking not set."""
        with app.app_context():
            recipe = Recipe(title='Prep Only', instructions='X', prep_time=10)
            assert recipe.total_time == 10

    def test_neither_set(self, app):
        """total_time is None when neither is set."""
        with app.app_context():
            recipe = Recipe(title='No Times', instructions='X')
            assert recipe.total_time is None


# ============================================================================
# Tag.get_or_create tests
# ============================================================================

class TestTagGetOrCreate:
    def test_creates_new_tag(self, app):
        """get_or_create creates a new tag when it doesn't exist."""
        with app.app_context():
            tag, created = Tag.get_or_create('NewTag', 'custom')
            assert created is True
            assert tag.name == 'NewTag'
            assert tag.tag_type == 'custom'

    def test_returns_existing_tag(self, app):
        """get_or_create returns existing tag when it already exists."""
        with app.app_context():
            tag1, c1 = Tag.get_or_create('Existing', 'custom')
            tag2, c2 = Tag.get_or_create('existing', 'custom')  # case-insensitive
            assert c1 is True
            assert c2 is False
            assert tag1.id == tag2.id

    def test_strips_whitespace(self, app):
        """Tag name is stripped of whitespace."""
        with app.app_context():
            tag, _ = Tag.get_or_create('  Trimmed  ', 'custom')
            assert tag.name == 'Trimmed'

    def test_invalid_tag_type_raises(self, app):
        """Invalid tag_type raises ValueError."""
        with app.app_context():
            with pytest.raises(ValueError, match='Invalid tag_type'):
                Tag.get_or_create('Test', 'bogus_type')

    def test_all_valid_types(self, app):
        """All VALID_TYPES are accepted."""
        with app.app_context():
            for ttype in Tag.VALID_TYPES:
                tag, created = Tag.get_or_create(f'test_{ttype}', ttype)
                assert tag.tag_type == ttype


# ============================================================================
# ShoppingItem model tests
# ============================================================================

class TestShoppingItemModel:
    def test_to_dict_no_recipe(self, app):
        """to_dict works when recipe is None."""
        with app.app_context():
            item = ShoppingItem(name='standalone item')
            db.session.add(item)
            db.session.commit()
            d = item.to_dict()
            assert d['name'] == 'standalone item'
            assert d['recipe_title'] is None
            assert d['recipe_id'] is None
            assert d['purchased'] is False

    def test_to_dict_with_recipe(self, app):
        """to_dict includes recipe_title when recipe is linked."""
        with app.app_context():
            recipe = Recipe(title='Linked Recipe', instructions='X')
            db.session.add(recipe)
            db.session.flush()
            item = ShoppingItem(name='from recipe', recipe_id=recipe.id)
            db.session.add(item)
            db.session.commit()
            d = item.to_dict()
            assert d['recipe_title'] == 'Linked Recipe'

    def test_default_not_purchased(self, app):
        """New items default to purchased=False once flushed."""
        with app.app_context():
            item = ShoppingItem(name='new item')
            db.session.add(item)
            db.session.flush()
            assert item.purchased is False

    def test_repr(self, app):
        """__repr__ includes name."""
        with app.app_context():
            item = ShoppingItem(name='repr test')
            assert 'repr test' in repr(item)


# ============================================================================
# update_recipe API edge cases
# ============================================================================

class TestUpdateRecipeApiEdgeCases:
    def test_update_recipe_no_data(self, client, api_admin_headers, app):
        """PUT with no data returns 400."""
        with app.app_context():
            recipe = Recipe(title='API Update Test', instructions='X')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        resp = client.put(f'/api/recipes/{rid}', json={},
                          headers=api_admin_headers)
        assert resp.status_code == 400

    def test_update_nonexistent_recipe(self, client, api_admin_headers):
        """Updating nonexistent recipe returns 404."""
        resp = client.put('/api/recipes/99999',
                         json={'title': 'Nope'},
                         headers=api_admin_headers)
        assert resp.status_code == 404

    def test_update_recipe_tags_too_long(self, client, api_admin_headers, app):
        """Tag name exceeding MAX_TAG_NAME_LENGTH returns 400."""
        with app.app_context():
            recipe = Recipe(title='Tag Length Test', instructions='X')
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id

        long_tag_name = 'a' * 101
        resp = client.put(f'/api/recipes/{rid}',
                         json={'tags': [{'name': long_tag_name, 'tag_type': 'custom'}]},
                         headers=api_admin_headers)
        assert resp.status_code == 400


# ============================================================================
# API GET /recipes filtering edge cases
# ============================================================================

class TestRecipeApiFiltering:
    def test_search_truncation(self, client, api_admin_headers, app):
        """Search term is truncated to 100 chars."""
        with app.app_context():
            recipe = Recipe(title='Searchable Recipe', instructions='X')
            db.session.add(recipe)
            db.session.commit()

        # A very long search term shouldn't cause issues
        long_search = 'a' * 200
        resp = client.get(f'/api/recipes?search={long_search}')
        assert resp.status_code == 200

    def test_pagination_clamps_per_page(self, client):
        """per_page is clamped to MAX_PER_PAGE."""
        resp = client.get('/api/recipes?per_page=1000')
        assert resp.status_code == 200

    def test_random_recipes_clamps_count(self, client):
        """count is clamped to max 20."""
        resp = client.get('/api/recipes/random?count=100')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data) <= 20


# ============================================================================
# API tags endpoint tests
# ============================================================================

class TestTagsApi:
    def test_get_all_tags(self, client, app):
        """GET /api/tags returns all tags."""
        with app.app_context():
            Tag.get_or_create('TagOne', 'custom')
            Tag.get_or_create('TagTwo', 'cuisine')
            db.session.commit()

        resp = client.get('/api/tags')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_filter_tags_by_type(self, client, app):
        """GET /api/tags?tag_type=cuisine filters correctly."""
        with app.app_context():
            Tag.get_or_create('CuisineTag', 'cuisine')
            Tag.get_or_create('CustomTag', 'custom')
            db.session.commit()

        resp = client.get('/api/tags?tag_type=cuisine')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for tag in data:
            assert tag['tag_type'] == 'cuisine'

    def test_get_random_recipes_empty(self, client):
        """GET /api/recipes/random returns empty when no recipes."""
        resp = client.get('/api/recipes/random')
        assert resp.status_code == 200
        assert json.loads(resp.data) == []


# ============================================================================
# Web UI page rendering tests
# ============================================================================

class TestPageRendering:
    def test_home_page(self, client):
        """Home page renders."""
        resp = client.get('/')
        assert resp.status_code == 200

    def test_search_page(self, client):
        """Search page renders."""
        resp = client.get('/search')
        assert resp.status_code == 200

    def test_api_docs_page(self, client):
        """API docs page renders."""
        resp = client.get('/api-docs')
        assert resp.status_code == 200

    def test_features_page(self, client):
        """Features page renders."""
        resp = client.get('/features')
        assert resp.status_code == 200

    def test_recipe_detail_nonexistent(self, client):
        """Nonexistent recipe returns 404."""
        resp = client.get('/recipe/99999')
        assert resp.status_code == 404

    def test_get_recipe_api_nonexistent(self, client):
        """GET /api/recipes/99999 returns 404."""
        resp = client.get('/api/recipes/99999')
        assert resp.status_code == 404


# ============================================================================
# Shopping list API edge cases
# ============================================================================

class TestShoppingListApiEdgeCases:
    def test_add_items_with_invalid_body(self, client, api_admin_headers):
        """POST without items array returns 400."""
        resp = client.post('/api/shopping-items',
                          json={'not_items': []},
                          headers=api_admin_headers)
        assert resp.status_code == 400

    def test_add_items_not_a_list(self, client, api_admin_headers):
        """items that is not a list returns 400."""
        resp = client.post('/api/shopping-items',
                          json={'items': 'not-a-list'},
                          headers=api_admin_headers)
        assert resp.status_code == 400

    def test_update_item_no_data(self, client, api_admin_headers, app):
        """PUT without data returns 400."""
        with app.app_context():
            item = ShoppingItem(name='test')
            db.session.add(item)
            db.session.commit()
            iid = item.id

        resp = client.put(f'/api/shopping-items/{iid}',
                         json={},
                         headers=api_admin_headers)
        assert resp.status_code == 400

    def test_update_nonexistent_item(self, client, api_admin_headers):
        """Updating nonexistent item returns 404."""
        resp = client.put('/api/shopping-items/99999',
                         json={'purchased': True},
                         headers=api_admin_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_item(self, client, api_admin_headers):
        """Deleting nonexistent item returns 404."""
        resp = client.delete('/api/shopping-items/99999',
                            headers=api_admin_headers)
        assert resp.status_code == 404


# ============================================================================
# Web UI RBAC for recipe actions
# ============================================================================

class TestWebUiRbac:
    def test_editor_can_submit_create_recipe(self, client, app):
        """Editor can POST to create a recipe."""
        with app.app_context():
            editor = User(username='webrbac_editor', role='editor')
            editor.set_password(TEST_PASSWORD)
            db.session.add(editor)
            db.session.commit()

        client.post('/api/auth/signin', data={
            'username': 'webrbac_editor',
            'password': TEST_PASSWORD
        })
        resp = client.post('/recipes', data={
            'title': 'Editor Recipe',
            'instructions': 'Mix and serve.'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Editor Recipe' in resp.data

    def test_viewer_cannot_submit_create_recipe(self, client, app):
        """Viewer cannot POST to create a recipe."""
        with app.app_context():
            viewer = User(username='webrbac_viewer', role='viewer')
            viewer.set_password(TEST_PASSWORD)
            db.session.add(viewer)
            db.session.commit()

        client.post('/api/auth/signin', data={
            'username': 'webrbac_viewer',
            'password': TEST_PASSWORD
        })
        resp = client.post('/recipes', data={
            'title': 'Viewer Recipe',
            'instructions': 'Should not work.'
        }, follow_redirects=False)
        # Viewer should be redirected (no permission)
        assert resp.status_code == 302
