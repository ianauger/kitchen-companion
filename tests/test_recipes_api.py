import pytest
from app.models import Recipe, Tag
from app import db

def test_add_tag_api(client, db_session):
    """Test that tags can be added via the POST /api/recipes/<id>/tags endpoint."""
    # Setup: Create a recipe
    recipe = Recipe(title="Test Recipe", instructions="Some instructions")
    db_session.add(recipe)
    db_session.commit()
    recipe_id = recipe.id

    # 1. Add a new tag
    response = client.post(f'/api/recipes/{recipe_id}/tags', json={'tag': '  Delicious  '})
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Delicious' # Normalized: stripped whitespace

    # Verify it's associated with the recipe
    recipe = Recipe.query.get(recipe_id)
    assert any(tag.name == 'Delicious' for tag in recipe.tags)

    # 2. Add the same tag again (should not create duplicate association)
    response = client.post(f'/api/recipes/{recipe_id}/tags', json={'tag': 'delicious'})
    assert response.status_code == 201
    
    recipe = Recipe.query.get(recipe_id)
    tags_list = [tag.name for tag in recipe.tags]
    assert tags_list.count('Delicious') == 1 # Only one association

    # 3. Add a different tag
    response = client.post(f'/api/recipes/{recipe_id}/tags', json={'tag': 'Quick'})
    assert response.status_code == 201
    
    recipe = Recipe.query.get(recipe_id)
    assert any(tag.name == 'Quick' for tag in recipe.tags)

def test_add_tag_invalid_requests(client, db_session):
    """Test invalid requests to the tag API."""
    recipe = Recipe(title="Test Recipe", instructions="Some instructions")
    db_session.add(recipe)
    db_session.commit()
    recipe_id = recipe.id

    # Missing tag name
    response = client.post(f'/api/recipes/{recipe_id}/tags', json={})
    assert response.status_code == 400

    # Empty tag name
    response = client.post(f'/api/recipes/{recipe_id}/tags', json={'tag': '   '})
    assert response.status_code == 400

    # Non-existent recipe
    response = client.post('/api/recipes/99999/tags', json={'tag': 'test'})
    assert response.status_code == 404
