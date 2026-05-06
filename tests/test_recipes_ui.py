"""Tests for recipe UI (web forms) functionality."""
import pytest
from app.models import Recipe, Tag
from app import db
import io


def test_create_recipe_form_page(auth_client):
    """Test that the create recipe form page loads correctly when authenticated."""
    response = auth_client.get('/recipes/new')
    assert response.status_code == 200
    assert b'Create New Recipe' in response.data
    assert b'Recipe Title' in response.data
    assert b'Cooking Instructions' in response.data
    assert b'Create Recipe' in response.data


def test_create_recipe_form_redirects_unauthenticated(client):
    """Test that create recipe form redirects to login when not authenticated."""
    response = client.get('/recipes/new')
    assert response.status_code == 302
    assert '/api/auth/signin' in response.location


def test_create_recipe_form_submission(auth_client, db_session):
    """Test creating a recipe through the web form."""
    response = auth_client.post('/recipes', data={
        'title': 'Test Spaghetti',
        'instructions': 'Boil pasta, add sauce, serve.',
        'ingredients': '- Pasta\n- Sauce',
        'difficulty': 'easy',
        'cooking_time': '20',
        'prep_time': '10',
        'servings': '4',
        'tags': 'Italian, Pasta, Quick'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Test Spaghetti' in response.data
    assert b'Boil pasta, add sauce, serve.' in response.data
    
    # Verify recipe was created
    recipe = Recipe.query.filter_by(title='Test Spaghetti').first()
    assert recipe is not None
    assert recipe.difficulty == 'easy'
    assert recipe.cooking_time == 20
    assert recipe.prep_time == 10
    assert recipe.servings == 4
    
    # Verify tags were created
    tag_names = [tag.name for tag in recipe.tags]
    assert 'Italian' in tag_names
    assert 'Pasta' in tag_names
    assert 'Quick' in tag_names


def test_create_recipe_missing_title(auth_client, db_session):
    """Test that form validation fails without title."""
    response = auth_client.post('/recipes', data={
        'instructions': 'Boil pasta, add sauce, serve.'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Should be redirected back to create form
    assert b'Create New Recipe' in response.data
    
    # Verify no recipe was created
    recipes = Recipe.query.filter_by(instructions='Boil pasta, add sauce, serve.').all()
    assert len(recipes) == 0


def test_create_recipe_missing_instructions(auth_client, db_session):
    """Test that form validation fails without instructions."""
    response = auth_client.post('/recipes', data={
        'title': 'Test Recipe'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Create New Recipe' in response.data
    
    # Verify no recipe was created
    recipe = Recipe.query.filter_by(title='Test Recipe').first()
    assert recipe is None


def test_edit_recipe_form_page(auth_client, db_session):
    """Test that the edit recipe form page loads with pre-populated data."""
    # Create a recipe
    recipe = Recipe(
        title='Original Title',
        instructions='Original instructions.',
        ingredients='Ingredient 1\nIngredient 2',
        difficulty='medium',
        cooking_time=30,
        prep_time=15,
        servings=4
    )
    db_session.add(recipe)
    db_session.commit()
    
    response = auth_client.get(f'/recipes/{recipe.id}/edit')
    assert response.status_code == 200
    assert b'Edit Recipe' in response.data
    assert b'Original Title' in response.data
    assert b'Original instructions.' in response.data
    assert b'Update Recipe' in response.data


def test_edit_recipe_form_submission(auth_client, db_session):
    """Test updating a recipe through the web form."""
    # Create initial recipe
    recipe = Recipe(
        title='Original Title',
        instructions='Original instructions.',
        difficulty='easy',
        cooking_time=20
    )
    db_session.add(recipe)
    db_session.commit()
    
    response = auth_client.post(f'/recipes/{recipe.id}', data={
        'title': 'Updated Title',
        'instructions': 'Updated instructions.',
        'ingredients': 'Updated ingredients',
        'difficulty': 'hard',
        'cooking_time': '45',
        'prep_time': '15',
        'servings': '6',
        'tags': 'Updated, New Tag'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Updated Title' in response.data
    assert b'Updated instructions.' in response.data
    
    # Verify recipe was updated
    updated_recipe = Recipe.query.get(recipe.id)
    assert updated_recipe.title == 'Updated Title'
    assert updated_recipe.instructions == 'Updated instructions.'
    assert updated_recipe.difficulty == 'hard'
    assert updated_recipe.cooking_time == 45
    assert updated_recipe.prep_time == 15
    assert updated_recipe.servings == 6
    
    # Verify tags were updated
    tag_names = [tag.name for tag in updated_recipe.tags]
    assert 'Updated' in tag_names
    assert 'New Tag' in tag_names


def test_edit_recipe_not_found(auth_client):
    """Test that editing a non-existent recipe returns 404."""
    response = auth_client.get('/recipes/99999/edit')
    assert response.status_code == 404


def test_edit_recipe_remove_tags(auth_client, db_session):
    """Test that tags can be removed from a recipe."""
    # Create recipe with tags
    recipe = Recipe(
        title='Tagged Recipe',
        instructions='Some instructions.'
    )
    db_session.add(recipe)
    db_session.flush()
    
    tag1 = Tag(name='Tag1', tag_type='custom')
    tag2 = Tag(name='Tag2', tag_type='custom')
    recipe.tags.extend([tag1, tag2])
    db_session.commit()
    
    # Update with empty tags
    response = auth_client.post(f'/recipes/{recipe.id}', data={
        'title': 'Tagged Recipe',
        'instructions': 'Some instructions.',
        'tags': ''
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify tags were removed
    updated_recipe = Recipe.query.get(recipe.id)
    assert len(updated_recipe.tags) == 0


def test_create_recipe_with_image_url(auth_client, db_session, mocker):
    """Test creating a recipe with an image URL."""
    # Mock the image download function
    mock_download = mocker.patch('app.routes.download_image')
    mock_download.return_value = ('uploads/recipes/recipe_1_test.jpg', '/path/to/file')
    
    mock_validate = mocker.patch('app.routes.validate_url')
    mock_validate.return_value = (True, None)
    
    response = auth_client.post('/recipes', data={
        'title': 'Recipe with Image',
        'instructions': 'Test instructions.',
        'image_url': 'https://example.com/image.jpg'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Use the actual mock object to check calls
    try:
        mock_validate.assert_called_once_with('https://example.com/image.jpg')
        mock_download.assert_called_once()
    except AssertionError as e:
        pytest.fail(f"Mock call failed: {e}")
    
    recipe = Recipe.query.filter_by(title='Recipe with Image').first()
    assert recipe is not None


def test_create_recipe_with_invalid_image_url(auth_client, db_session, mocker):
    """Test that invalid image URLs are handled gracefully."""
    # Mock the URL validation to fail
    mock_validate = mocker.patch('app.routes.validate_url')
    mock_validate.return_value = (False, 'Invalid URL')
    
    response = auth_client.post('/recipes', data={
        'title': 'Recipe with Bad Image',
        'instructions': 'Test instructions.',
        'image_url': 'not-a-valid-url'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    recipe = Recipe.query.filter_by(title='Recipe with Bad Image').first()
    assert recipe is not None
    assert recipe.image_path is None


def test_recipe_detail_has_edit_button(client, db_session):
    """Test that the recipe detail page has an Edit button."""
    recipe = Recipe(
        title='Viewable Recipe',
        instructions='Instructions here.'
    )
    db_session.add(recipe)
    db_session.commit()
    
    response = client.get(f'/recipe/{recipe.id}')
    assert response.status_code == 200
    assert b'Edit Recipe' in response.data
    assert f'/recipes/{recipe.id}/edit'.encode() in response.data


def test_layout_has_create_recipe_link(client):
    """Test that the layout includes a Create Recipe link."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Create Recipe' in response.data
    assert b'/recipes/new' in response.data


def test_create_recipe_with_file_upload(auth_client, db_session, mocker):
    """Test creating a recipe with a file upload."""
    # Mock the save_uploaded_image function
    mock_save = mocker.patch('app.routes.save_uploaded_image')
    mock_save.return_value = ('uploads/recipes/recipe_1_uploaded.jpg', None)
    
    # Create a test file
    data = {
        'title': 'Recipe with File Upload',
        'instructions': 'Test instructions.',
        'image_file': (io.BytesIO(b'fake-image-data'), 'test_image.jpg')
    }
    
    response = auth_client.post(
        '/recipes',
        data=data,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    recipe = Recipe.query.filter_by(title='Recipe with File Upload').first()
    assert recipe is not None


def test_update_recipe_preserves_other_fields(auth_client, db_session):
    """Test that updating a recipe doesn't reset unspecified fields."""
    recipe = Recipe(
        title='Original Title',
        instructions='Original instructions.',
        ingredients='Original ingredients',
        source_url='https://example.com/original',
        difficulty='medium',
        cooking_time=30,
        prep_time=15,
        servings=4
    )
    db_session.add(recipe)
    db_session.commit()
    
    # Update only the title
    response = auth_client.post(f'/recipes/{recipe.id}', data={
        'title': 'New Title',
        'instructions': 'Original instructions.',
        'ingredients': 'Original ingredients',
        'difficulty': 'medium'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    updated = Recipe.query.get(recipe.id)
    assert updated.title == 'New Title'
    assert updated.source_url == 'https://example.com/original'
    assert updated.cooking_time == 30
    assert updated.prep_time == 15
    assert updated.servings == 4


def test_create_recipe_empty_tags(auth_client, db_session):
    """Test that empty tag strings don't create empty tags."""
    response = auth_client.post('/recipes', data={
        'title': 'No Tags Recipe',
        'instructions': 'Some instructions.',
        'tags': '  , ,   '
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    recipe = Recipe.query.filter_by(title='No Tags Recipe').first()
    assert recipe is not None
    assert len(recipe.tags) == 0
