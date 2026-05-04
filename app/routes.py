"""Route handlers for Kitchen Companion application."""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import Recipe, Tag, Note, ShoppingItem
from app.image_utils import download_image, delete_image, validate_url, get_upload_dir
from config import (
    MAX_NOTE_LENGTH, MAX_TAG_NAME_LENGTH,
    DEFAULT_PER_PAGE, MAX_PER_PAGE
)
from sqlalchemy.orm import joinedload
import os
from datetime import datetime

# Blueprint for main pages
main_bp = Blueprint('main', __name__)

# Blueprint for API endpoints
api_bp = Blueprint('api', __name__)


# ============================================================================
# Main Page Routes
# ============================================================================

@main_bp.route('/')
def index():
    """Render the home page with a random selection of 6 recipes."""
    from sqlalchemy import func
    # Eager load tags and notes to avoid N+1 queries
    recipes_list = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).order_by(func.random()).limit(6).all()
    return render_template('home.html', recipes=recipes_list)


@main_bp.route('/recipe/<int:recipe_id>')
def get_recipe_detail(recipe_id):
    """Render the detailed view of a single recipe."""
    # Eager load tags and notes to avoid N+1 queries
    recipe = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).get_or_404(recipe_id)
    return render_template('recipe_detail.html', recipe=recipe)


@main_bp.route('/search')
def search():
    """Render the search page with all tags for filtering."""
    tags = Tag.query.all()
    # Group tags by type for the filter UI
    tags_by_type = {}
    for tag in tags:
        tags_by_type.setdefault(tag.tag_type, []).append(tag)
    return render_template('search.html', tags_by_type=tags_by_type, tags=tags)


@main_bp.route('/api-docs')
def api_docs():
    """Render the API reference page."""
    return render_template('api_docs.html')


@main_bp.route('/shopping-list')
def shopping_list():
    """Render the shopping list page."""
    from sqlalchemy.orm import joinedload
    items = ShoppingItem.query.options(
        joinedload(ShoppingItem.recipe)
    ).order_by(ShoppingItem.purchased.asc(), ShoppingItem.created_at.desc()).all()
    return render_template('shopping_list.html', items=items)


@main_bp.route('/features')
def features():
    """Render the features page."""
    return render_template('features.html')


# ============================================================================
# Recipe Form Routes (Create & Edit)
# ============================================================================

@main_bp.route('/recipes/new', methods=['GET'])
def create_recipe_form():
    """Render the form for creating a new recipe."""
    # Get all tags grouped by type for the tag selector
    tags = Tag.query.all()
    tags_by_type = {}
    for tag in tags:
        tags_by_type.setdefault(tag.tag_type, []).append(tag)
    return render_template('recipe_form.html', tags_by_type=tags_by_type, recipe=None)


@main_bp.route('/recipes/<int:recipe_id>/edit', methods=['GET'])
def edit_recipe_form(recipe_id):
    """Render the form for editing an existing recipe."""
    recipe = Recipe.query.options(
        joinedload(Recipe.tags)
    ).get_or_404(recipe_id)
    
    # Get all tags grouped by type for the tag selector
    tags = Tag.query.all()
    tags_by_type = {}
    for tag in tags:
        tags_by_type.setdefault(tag.tag_type, []).append(tag)
    
    # Get current recipe tags as comma-separated string
    recipe_tags_str = ', '.join([tag.name for tag in recipe.tags])
    
    return render_template('recipe_form.html', 
                          tags_by_type=tags_by_type, 
                          recipe=recipe,
                          recipe_tags_str=recipe_tags_str)


@main_bp.route('/recipes', methods=['POST'])
@limiter.limit("10 per minute")
def create_recipe_submit():
    """Handle form submission for creating a new recipe."""
    from flask import current_app
    
    # Validate required fields
    title = request.form.get('title', '').strip()
    instructions = request.form.get('instructions', '').strip()
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('main.create_recipe_form'))
    if not instructions:
        flash('Instructions are required', 'error')
        return redirect(url_for('main.create_recipe_form'))
    
    # Create recipe
    recipe = Recipe(
        title=title,
        instructions=instructions,
        ingredients=request.form.get('ingredients', '').strip(),
        source_url=request.form.get('source_url', '').strip() or None,
        cooking_time=request.form.get('cooking_time', type=int),
        prep_time=request.form.get('prep_time', type=int),
        servings=request.form.get('servings', type=int),
        difficulty=request.form.get('difficulty', 'medium')
    )
    
    try:
        db.session.add(recipe)
        db.session.flush()  # Get the recipe ID
        
        # Handle tags (comma-separated values)
        tags_input = request.form.get('tags', '').strip()
        if tags_input:
            tag_names = [name.strip() for name in tags_input.split(',') if name.strip()]
            for tag_name in tag_names:
                if tag_name and len(tag_name) <= MAX_TAG_NAME_LENGTH:
                    tag, _ = Tag.get_or_create(name=tag_name, tag_type='custom')
                    recipe.tags.append(tag)
        
        # Handle image upload from file
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                relative_path, error = save_uploaded_image(file, recipe.id)
                if relative_path:
                    recipe.image_path = relative_path
                elif error:
                    current_app.logger.warning(f'Image upload failed: {error}')
        
        # Handle image URL if provided
        if not recipe.image_path:
            image_url = request.form.get('image_url', '').strip()
            if image_url:
                is_valid, error_msg = validate_url(image_url)
                if is_valid:
                    relative_path, _ = download_image(image_url, recipe_id=recipe.id)
                    if relative_path:
                        recipe.image_path = relative_path
                        recipe.image_url = image_url
                else:
                    current_app.logger.warning(f'Invalid image URL: {error_msg}')
        
        db.session.commit()
        flash('Recipe created successfully!', 'success')
        return redirect(url_for('main.get_recipe_detail', recipe_id=recipe.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to create recipe: {e}')
        flash('Failed to create recipe. Please try again.', 'error')
        return redirect(url_for('main.create_recipe_form'))


@main_bp.route('/recipes/<int:recipe_id>', methods=['POST'])
@limiter.limit("10 per minute")
def update_recipe_submit(recipe_id):
    """Handle form submission for updating an existing recipe."""
    from flask import current_app
    
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Validate required fields
    title = request.form.get('title', '').strip()
    instructions = request.form.get('instructions', '').strip()
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))
    if not instructions:
        flash('Instructions is required', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))
    
    # Update fields only if provided in the request
    title = request.form.get('title', '').strip()
    if title:
        recipe.title = title
    
    instructions = request.form.get('instructions', '').strip()
    if instructions:
        recipe.instructions = instructions
    
    ingredients = request.form.get('ingredients', '').strip()
    if ingredients:
        recipe.ingredients = ingredients
        
    source_url = request.form.get('source_url', '').strip()
    if source_url:
        recipe.source_url = source_url
    elif request.form.get('clear_source'):
        recipe.source_url = None

    # For numeric fields, check if they are present and not empty strings
    cooking_time = request.form.get('cooking_time')
    if cooking_time is not None and cooking_time != '':
        recipe.cooking_time = int(cooking_time)
        
    prep_time = request.form.get('prep_time')
    if prep_time is not None and prep_time != '':
        recipe.prep_time = int(prep_time)
        
    servings = request.form.get('servings')
    if servings is not None and servings != '':
        recipe.servings = int(servings)
        
    difficulty = request.form.get('difficulty')
    if difficulty:
        recipe.difficulty = difficulty
        
    recipe.updated_at = datetime.utcnow()
    
    try:
        # Handle tags (comma-separated values)
        tags_input = request.form.get('tags', '').strip()
        recipe.tags = []  # Clear existing tags
        if tags_input:
            tag_names = [name.strip() for name in tags_input.split(',') if name.strip()]
            for tag_name in tag_names:
                if tag_name and len(tag_name) <= MAX_TAG_NAME_LENGTH:
                    tag, _ = Tag.get_or_create(name=tag_name, tag_type='custom')
                    recipe.tags.append(tag)
        
        # Handle image upload from file
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                # Delete old image if exists
                if recipe.image_path:
                    delete_image(recipe.image_path)
                relative_path, error = save_uploaded_image(file, recipe.id)
                if relative_path:
                    recipe.image_path = relative_path
                elif error:
                    current_app.logger.warning(f'Image upload failed: {error}')
        
        # Handle image URL if provided and file not uploaded
        elif not recipe.image_path or request.form.get('clear_image'):
            image_url = request.form.get('image_url', '').strip()
            if image_url:
                is_valid, error_msg = validate_url(image_url)
                if is_valid:
                    # Delete old image if exists
                    if recipe.image_path:
                        delete_image(recipe.image_path)
                    relative_path, _ = download_image(image_url, recipe_id=recipe.id)
                    if relative_path:
                        recipe.image_path = relative_path
                        recipe.image_url = image_url
                else:
                    current_app.logger.warning(f'Invalid image URL: {error_msg}')
        
        # Handle image clearing
        if request.form.get('clear_image') and recipe.image_path:
            delete_image(recipe.image_path)
            recipe.image_path = None
            recipe.image_url = None
        
        db.session.commit()
        flash('Recipe updated successfully!', 'success')
        return redirect(url_for('main.get_recipe_detail', recipe_id=recipe_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to update recipe: {e}')
        flash('Failed to update recipe. Please try again.', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))


def save_uploaded_image(file, recipe_id):
    """Save an uploaded image file.
    
    Args:
        file: The uploaded file object
        recipe_id: The recipe ID for filename
        
    Returns:
        tuple: (relative_path, error_message) - relative_path is None on failure
    """
    from flask import current_app
    import uuid
    from pathlib import Path
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    if not file.filename:
        return None, "No file selected"
    
    # Get file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        return None, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
    
    # Generate filename
    filename = f'recipe_{recipe_id}_{uuid.uuid4().hex[:8]}{ext}'
    upload_dir = get_upload_dir()
    absolute_path = upload_dir / filename
    relative_path = f'uploads/recipes/{filename}'
    
    try:
        file.save(str(absolute_path))
        return relative_path, None
    except Exception as e:
        return None, str(e)


# ============================================================================
# API Routes
# ============================================================================

@api_bp.route('/recipes', methods=['GET'])
def get_recipes():
    """Get all recipes with optional filtering.
    
    Query Parameters:
        tag: Filter by tag name
        tag_type: Filter by tag type
        difficulty: Filter by difficulty level
        search: Search recipes by title (case-insensitive partial match)
        max_prep_time: Filter by maximum prep time (minutes)
        max_cooking_time: Filter by maximum cooking time (minutes)
        max_total_time: Filter by maximum total time (prep + cooking)
        page: Page number for pagination (default: 1)
        per_page: Items per page (default: 20, max: 100)
    
    Returns:
        JSON object with recipes array and pagination info
    """
    from sqlalchemy import func, and_
    
    # Eager load tags and notes to avoid N+1 queries
    query = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    )
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE)
    
    # Apply filters if provided
    tag_name = request.args.get('tag')
    tag_type = request.args.get('tag_type')
    difficulty = request.args.get('difficulty')
    search_term = request.args.get('search')
    max_prep_time = request.args.get('max_prep_time', type=int)
    max_cooking_time = request.args.get('max_cooking_time', type=int)
    max_total_time = request.args.get('max_total_time', type=int)
    
    if tag_name:
        query = query.filter(Recipe.tags.any(name=tag_name))
    if tag_type:
        query = query.filter(Recipe.tags.any(tag_type=tag_type))
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if search_term:
        # Limit search term length to prevent potential issues
        search_term = search_term[:100]
        query = query.filter(Recipe.title.ilike(f'%{search_term}%'))
    
    # Filter by prep time - exclude NULL values when filtering
    if max_prep_time is not None:
        query = query.filter(
            and_(Recipe.prep_time.isnot(None), Recipe.prep_time <= max_prep_time)
        )
    
    # Filter by cooking time - exclude NULL values when filtering
    if max_cooking_time is not None:
        query = query.filter(
            and_(Recipe.cooking_time.isnot(None), Recipe.cooking_time <= max_cooking_time)
        )
    
    # Filter by total time - exclude NULL values when filtering
    if max_total_time is not None:
        query = query.filter(
            and_(
                Recipe.prep_time.isnot(None),
                Recipe.cooking_time.isnot(None),
                (Recipe.prep_time + Recipe.cooking_time) <= max_total_time
            )
        )
    
    # Apply pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'recipes': [recipe.to_dict() for recipe in pagination.items],
        'pagination': {
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@api_bp.route('/recipes', methods=['POST'])
@limiter.limit("10 per minute")
def create_recipe():
    """Create a new recipe.
    
    Request Body (JSON):
        title: (required) Recipe name
        instructions: (required) Cooking instructions
        source_url: (optional) Source URL
        image_url: (optional) URL of recipe cover image — will be downloaded locally
        cooking_time: (optional) Cooking time in minutes
        prep_time: (optional) Prep time in minutes
        servings: (optional) Number of servings
        difficulty: (optional) Difficulty level (easy/medium/hard)
        tags: (optional) Array of tag objects {name, tag_type}
    
    Returns:
        JSON object of created recipe with 201 status
    """
    from flask import current_app
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    if 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    if 'instructions' not in data:
        return jsonify({'error': 'Instructions are required'}), 400
    
    # Validate image_url if provided (SSRF prevention)
    image_url = data.get('image_url')
    if image_url:
        is_valid, error_msg = validate_url(image_url)
        if not is_valid:
            return jsonify({
                'error': 'Invalid image URL',
                'details': error_msg
            }), 400
    
    recipe = None
    try:
        # Create recipe
        recipe = Recipe(
            title=data['title'],
            instructions=data['instructions'],
            ingredients=data.get('ingredients'),
            source_url=data.get('source_url'),
            image_url=image_url,
            cooking_time=data.get('cooking_time'),
            prep_time=data.get('prep_time'),
            servings=data.get('servings'),
            difficulty=data.get('difficulty', 'medium')
        )
        
        # Handle tags using get_or_create method
        if 'tags' in data:
            for tag_data in data['tags']:
                # Validate tag name length
                tag_name = tag_data.get('name', '')
                if len(tag_name) > MAX_TAG_NAME_LENGTH:
                    db.session.rollback()
                    return jsonify({
                        'error': f'Tag name exceeds maximum length of {MAX_TAG_NAME_LENGTH} characters'
                    }), 400
                tag, _ = Tag.get_or_create(
                    name=tag_name,
                    tag_type=tag_data.get('tag_type', 'custom')
                )
                recipe.tags.append(tag)
        
        db.session.add(recipe)
        db.session.flush()  # Get the recipe ID before downloading image
        
        # Download image if URL provided
        image_downloaded = False
        if image_url:
            relative_path, error_msg = download_image(image_url, recipe_id=recipe.id)
            if relative_path:
                recipe.image_path = relative_path
                recipe.image_url = image_url
                image_downloaded = True
            else:
                # Log warning but don't fail - recipe is created without image
                current_app.logger.warning(
                    f'Failed to download image for recipe {recipe.id}: {error_msg}'
                )
        
        db.session.commit()
        
        response_data = recipe.to_dict()
        if image_url and not image_downloaded:
            response_data['warning'] = 'Recipe created but image download failed'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to create recipe: {e}')
        return jsonify({'error': 'Failed to create recipe'}), 500


@api_bp.route('/recipes/<int:recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    """Get a specific recipe by ID.
    
    Args:
        recipe_id: Recipe ID
    
    Returns:
        JSON object of the recipe or 404 error
    """
    # Eager load tags and notes to avoid N+1 queries
    recipe = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).get_or_404(recipe_id)
    return jsonify(recipe.to_dict())


@api_bp.route('/recipes/<int:recipe_id>', methods=['PUT'])
def update_recipe(recipe_id):
    """Update an existing recipe.
    
    Args:
        recipe_id: Recipe ID
    
    Request Body (JSON):
        Any recipe fields to update.
        If image_url is provided and differs from current, the new image
        will be downloaded and the old local image deleted.
    
    Returns:
        JSON object of updated recipe
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Update fields
    for field in ['title', 'instructions', 'ingredients', 'source_url', 'cooking_time', 
                   'prep_time', 'servings', 'difficulty']:
        if field in data:
            setattr(recipe, field, data[field])
    
    # Handle image update
    new_image_url = data.get('image_url')
    if new_image_url and new_image_url != recipe.image_url:
        # Validate new image URL (SSRF prevention)
        is_valid, error_msg = validate_url(new_image_url)
        if not is_valid:
            return jsonify({
                'error': 'Invalid image URL',
                'details': error_msg
            }), 400
        
        # Delete old image file if it exists
        if recipe.image_path:
            delete_image(recipe.image_path)
        # Download new image
        relative_path, _ = download_image(new_image_url, recipe_id=recipe.id)
        recipe.image_url = new_image_url
        recipe.image_path = relative_path
    
    # Update tags if provided using get_or_create method
    if 'tags' in data:
        recipe.tags = []
        for tag_data in data['tags']:
            # Validate tag name length
            tag_name = tag_data.get('name', '')
            if len(tag_name) > MAX_TAG_NAME_LENGTH:
                return jsonify({
                    'error': f'Tag name exceeds maximum length of {MAX_TAG_NAME_LENGTH} characters'
                }), 400
            tag, _ = Tag.get_or_create(
                name=tag_name,
                tag_type=tag_data.get('tag_type', 'custom')
            )
            recipe.tags.append(tag)
    
    db.session.commit()
    return jsonify(recipe.to_dict())


@api_bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    """Delete a recipe.
    
    Also deletes the locally stored cover image if it exists.
    
    Args:
        recipe_id: Recipe ID
    
    Returns:
        Empty response with 204 status
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Clean up local image
    if recipe.image_path:
        delete_image(recipe.image_path)
    
    db.session.delete(recipe)
    db.session.commit()
    return '', 204


@api_bp.route('/tags', methods=['GET'])
def get_tags():
    """Get all tags.
    
    Query Parameters:
        tag_type: Filter by tag type
    
    Returns:
        JSON array of tags
    """
    tag_type = request.args.get('tag_type')
    
    if tag_type:
        tags = Tag.query.filter_by(tag_type=tag_type).all()
    else:
        tags = Tag.query.all()
    
    return jsonify([tag.to_dict() for tag in tags])


@api_bp.route('/recipes/random', methods=['GET'])
def get_random_recipes():
    """Get a random selection of recipes.
    
    Query Parameters:
        count: Number of recipes to return (default 6, max 20)
    
    Returns:
        JSON array of recipes
    """
    from sqlalchemy import func
    count = min(request.args.get('count', 6, type=int), 20)
    # Use database-level random sampling with eager loading
    recipes = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).order_by(func.random()).limit(count).all()
    return jsonify([recipe.to_dict() for recipe in recipes])


# ============================================================================
# Shopping List API Routes
# ============================================================================

@api_bp.route('/shopping-items', methods=['GET'])
def get_shopping_items():
    """Get all shopping list items."""
    from sqlalchemy.orm import joinedload
    purchased_filter = request.args.get('purchased', 'all')
    query = ShoppingItem.query.options(joinedload(ShoppingItem.recipe))
    if purchased_filter == 'true':
        query = query.filter_by(purchased=True)
    elif purchased_filter == 'false':
        query = query.filter_by(purchased=False)
    items = query.order_by(ShoppingItem.purchased.asc(), ShoppingItem.created_at.desc()).all()
    return jsonify([item.to_dict() for item in items])


@api_bp.route('/shopping-items', methods=['POST'])
@limiter.limit("30 per minute")
def add_shopping_items():
    """Add items to the shopping list."""
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'items array is required'}), 400
    if not isinstance(data['items'], list):
        return jsonify({'error': 'items must be an array'}), 400

    added = []
    try:
        for item_data in data['items']:
            name = item_data.get('name', '').strip()
            if not name:
                continue
            ri = item_data.get('recipe_id')
            existing = ShoppingItem.query.filter(
                db.func.lower(ShoppingItem.name) == db.func.lower(name),
                ShoppingItem.purchased == False
            ).first()
            if existing:
                continue

            item = ShoppingItem(name=name, recipe_id=ri if ri else None)
            db.session.add(item)
            db.session.flush()
            added.append(item.to_dict())

        db.session.commit()
        return jsonify({'items': added, 'count': len(added)}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to add shopping items: {e}')
        return jsonify({'error': 'Failed to add items'}), 500


@api_bp.route('/shopping-items/<int:item_id>', methods=['PUT'])
def update_shopping_item(item_id):
    """Update a shopping item."""
    item = ShoppingItem.query.get_or_404(item_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if 'purchased' in data:
        item.purchased = bool(data['purchased'])
    if 'name' in data and data['name'].strip():
        item.name = data['name'].strip()
    db.session.commit()
    return jsonify(item.to_dict())


@api_bp.route('/shopping-items/<int:item_id>', methods=['DELETE'])
def delete_shopping_item(item_id):
    """Delete a shopping item."""
    item = ShoppingItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return '', 204


@api_bp.route('/shopping-items/clear-purchased', methods=['POST'])
def clear_purchased_items():
    """Remove all purchased items."""
    count = ShoppingItem.query.filter_by(purchased=True).delete()
    db.session.commit()
    return jsonify({'deleted': count})


# ============================================================================
# Notes API Routes
# ============================================================================

@api_bp.route('/recipes/<int:recipe_id>/notes', methods=['GET'])
def get_recipe_notes(recipe_id):
    """Get all notes for a recipe.
    
    Args:
        recipe_id: Recipe ID
    
    Returns:
        JSON array of notes
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    # Notes are now ordered by created_at.desc() via the relationship
    return jsonify([note.to_dict() for note in recipe.notes])


@api_bp.route('/recipes/<int:recipe_id>/notes', methods=['POST'])
@limiter.limit("30 per minute")
def create_note(recipe_id):
    """Create a new note for a recipe.
    
    Args:
        recipe_id: Recipe ID
    
    Request Body (JSON):
        content: (required) Note content
    
    Returns:
        JSON object of created note with 201 status
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'content' not in data or not data['content'].strip():
        return jsonify({'error': 'Content is required'}), 400
    
    # Validate note content length
    if len(data['content']) > MAX_NOTE_LENGTH:
        return jsonify({
            'error': f'Note exceeds maximum length of {MAX_NOTE_LENGTH} characters'
        }), 400
    
    note = Note(
        recipe_id=recipe_id,
        content=data['content'].strip()
    )
    
    db.session.add(note)
    db.session.commit()
    
    return jsonify(note.to_dict()), 201


@api_bp.route('/notes/<int:note_id>', methods=['PUT'])
@limiter.limit("30 per minute")
def update_note(note_id):
    """Update an existing note.
    
    Args:
        note_id: Note ID
    
    Request Body (JSON):
        content: (required) Updated note content
    
    Returns:
        JSON object of updated note
    """
    note = Note.query.get_or_404(note_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'content' not in data or not data['content'].strip():
        return jsonify({'error': 'Content is required'}), 400
    
    # Validate note content length
    if len(data['content']) > MAX_NOTE_LENGTH:
        return jsonify({
            'error': f'Note exceeds maximum length of {MAX_NOTE_LENGTH} characters'
        }), 400
    
    note.content = data['content'].strip()
    db.session.commit()
    
    return jsonify(note.to_dict())


@api_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a note.
    
    Args:
        note_id: Note ID
    
    Returns:
        Empty response with 204 status
    """
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return '', 204


@api_bp.route('/recipes/<int:recipe_id>/tags', methods=['POST'])
@limiter.limit("20 per minute")
def add_recipe_tag(recipe_id):
    """Add a tag to a recipe.
    
    Args:
        recipe_id: Recipe ID
    
    Request Body (JSON):
        tag: (required) Tag name
    
    Returns:
        JSON object of the added tag with 201 status
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    data = request.get_json()
    
    if not data or 'tag' not in data:
        return jsonify({'error': 'Tag name is required'}), 400
    
    tag_name = data['tag'].strip()
    if not tag_name:
        return jsonify({'error': 'Tag name cannot be empty'}), 400
    
    if len(tag_name) > MAX_TAG_NAME_LENGTH:
        return jsonify({'error': f'Tag name exceeds maximum length of {MAX_TAG_NAME_LENGTH} characters'}), 400
    
    try:
        # Use the model's get_or_create method (normalizes and checks for existence)
        tag, created = Tag.get_or_create(name=tag_name, tag_type='custom')
        
        # Avoid duplicates for the same recipe
        if tag not in recipe.tags:
            recipe.tags.append(tag)
            db.session.commit()
        
        return jsonify(tag.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to add tag to recipe {recipe_id}: {e}')
        return jsonify({'error': 'Failed to add tag'}), 500

