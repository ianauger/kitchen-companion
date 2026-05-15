"""Route handlers for Kitchen Companion application."""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import Recipe, Tag, Note, ShoppingItem
from app.auth import editor_or_admin, admin_required, login_required_web, editor_or_admin_web
from app.image_utils import download_image, delete_image, validate_url, get_upload_dir
from config import (
    MAX_NOTE_LENGTH, MAX_TAG_NAME_LENGTH,
    DEFAULT_PER_PAGE, MAX_PER_PAGE
)
from sqlalchemy.orm import joinedload, selectinload
import os
import random
from datetime import datetime, timezone

# Blueprint for main pages
main_bp = Blueprint('main', __name__)

# Blueprint for API endpoints
api_bp = Blueprint('api', __name__)


# ============================================================================
# Helpers
# ============================================================================

def _random_recipes(count: int):
    """Return up to *count* randomly sampled recipes with tags and notes loaded.

    Samples from all recipe IDs in Python rather than using ORDER BY RANDOM(),
    which is a full-table sort and degrades linearly with table size.
    """
    id_rows = db.session.query(Recipe.id).all()
    if not id_rows:
        return []
    sampled_ids = random.sample([r[0] for r in id_rows], min(count, len(id_rows)))
    return (
        Recipe.query
        .options(joinedload(Recipe.tags), joinedload(Recipe.notes))
        .filter(Recipe.id.in_(sampled_ids))
        .all()
    )


# ============================================================================
# Main Page Routes
# ============================================================================

@main_bp.route('/health')
def health():
    """Healthcheck endpoint for container orchestration."""
    try:
        # Verify DB connectivity
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'healthy'}), 200
    except Exception:
        return jsonify({'status': 'unhealthy'}), 503


@main_bp.route('/')
def index():
    """Render the home page with a random selection of 6 recipes."""
    recipes_list = _random_recipes(6)
    return render_template('home.html', recipes=recipes_list)


@main_bp.route('/recipe/<int:recipe_id>')
def get_recipe_detail(recipe_id):
    """Render the detailed view of a single recipe."""
    recipe = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).filter_by(id=recipe_id).first_or_404()
    return render_template('recipe_detail.html', recipe=recipe)


@main_bp.route('/recipe/<int:recipe_id>/cook')
def get_execution_view(recipe_id):
    """Render the cooking execution view (step-by-step mode)."""
    recipe = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).get_or_404(recipe_id)
    return render_template('execution.html', recipe=recipe)


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
    items = ShoppingItem.query.options(
        joinedload(ShoppingItem.recipe)
    ).order_by(ShoppingItem.purchased.asc(), ShoppingItem.created_at.desc()).all()
    return render_template('shopping_list.html', items=items)


# ============================================================================
# Shopping List Web UI Routes (session-based auth)
# ============================================================================

@main_bp.route('/shopping-items', methods=['GET'])
def get_shopping_items_web():
    """Get all shopping list items (web UI, no auth required for GET)."""
    items = ShoppingItem.query.options(
        joinedload(ShoppingItem.recipe)
    ).order_by(ShoppingItem.purchased.asc(), ShoppingItem.created_at.desc()).all()
    return jsonify([item.to_dict() for item in items])


@main_bp.route('/shopping-items', methods=['POST'])
@limiter.limit("30 per minute")
@editor_or_admin_web
def add_shopping_items_web():
    # TODO: merge with add_shopping_items() — both functions share identical logic
    """Add items to the shopping list (web UI, session auth)."""
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'items array is required'}), 400
    if not isinstance(data['items'], list):
        return jsonify({'error': 'items must be an array'}), 400

    added = []
    try:
        for item_data in data['items']:
            # Normalize: collapse whitespace for consistent comparison
            name = ' '.join(item_data.get('name', '').split())
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
        current_app.logger.error(f'Failed to add shopping items (web): {e}')
        return jsonify({'error': 'Failed to add items'}), 500


@main_bp.route('/shopping-items/<int:item_id>', methods=['PUT'])
@editor_or_admin_web
def update_shopping_item_web(item_id):
    """Update a shopping item (web UI, session auth)."""
    item = db.get_or_404(ShoppingItem, item_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if 'purchased' in data:
        item.purchased = bool(data['purchased'])
    if 'name' in data and data['name'].strip():
        item.name = data['name'].strip()
    db.session.commit()
    return jsonify(item.to_dict())


@main_bp.route('/shopping-items/<int:item_id>/delete', methods=['POST'])
@editor_or_admin_web
def delete_shopping_item_web(item_id):
    """Delete a shopping item (web UI, session auth)."""
    item = db.get_or_404(ShoppingItem, item_id)
    db.session.delete(item)
    db.session.commit()
    return '', 204


@main_bp.route('/shopping-items/clear-purchased', methods=['POST'])
@editor_or_admin_web
def clear_purchased_items_web():
    """Delete all purchased items (web UI, session auth)."""
    deleted = ShoppingItem.query.filter_by(purchased=True).delete()
    db.session.commit()
    return jsonify({'deleted': deleted}), 200


@main_bp.route('/features')
def features():
    """Render the features page."""
    return render_template('features.html')


# ============================================================================
# Recipe Form Routes (Create & Edit)
# ============================================================================

@main_bp.route('/recipes/new', methods=['GET'])
@login_required_web
def create_recipe_form():
    """Render the form for creating a new recipe."""
    # Get all tags grouped by type for the tag selector
    tags = Tag.query.all()
    tags_by_type = {}
    for tag in tags:
        tags_by_type.setdefault(tag.tag_type, []).append(tag)
    return render_template('recipe_form.html', tags_by_type=tags_by_type, recipe=None)


@main_bp.route('/recipes/<int:recipe_id>/edit', methods=['GET'])
@login_required_web
def edit_recipe_form(recipe_id):
    """Render the form for editing an existing recipe."""
    recipe = Recipe.query.options(
        joinedload(Recipe.tags)
    ).filter_by(id=recipe_id).first_or_404()
    
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
@editor_or_admin_web
def create_recipe_submit():
    """Handle form submission for creating a new recipe."""
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
@editor_or_admin_web
def update_recipe_submit(recipe_id):
    """Handle form submission for updating an existing recipe."""
    recipe = db.get_or_404(Recipe, recipe_id)
    
    # Validate and extract required fields
    title = request.form.get('title', '').strip()
    instructions = request.form.get('instructions', '').strip()
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))
    if not instructions:
        flash('Instructions is required', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))
    
    # Update fields — required fields already validated above
    recipe.title = title
    recipe.instructions = instructions
    
    recipe.ingredients = request.form.get('ingredients', '').strip() or None
        
    source_url = request.form.get('source_url', '').strip()
    if source_url:
        recipe.source_url = source_url
    elif request.form.get('clear_source'):
        recipe.source_url = None

    cooking_time = request.form.get('cooking_time', type=int)
    if cooking_time is not None:
        recipe.cooking_time = cooking_time

    prep_time = request.form.get('prep_time', type=int)
    if prep_time is not None:
        recipe.prep_time = prep_time

    servings = request.form.get('servings', type=int)
    if servings is not None:
        recipe.servings = servings
        
    difficulty = request.form.get('difficulty')
    if difficulty:
        recipe.difficulty = difficulty
        
    recipe.updated_at = datetime.now(timezone.utc)
    
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
        
        # Image update: file upload > explicit clear > URL replacement (mutually exclusive)
        uploaded_file = request.files.get('image_file')
        if uploaded_file and uploaded_file.filename:
            if recipe.image_path:
                delete_image(recipe.image_path)
            relative_path, error = save_uploaded_image(uploaded_file, recipe.id)
            if relative_path:
                recipe.image_path = relative_path
                recipe.image_url = None
            elif error:
                current_app.logger.warning(f'Image upload failed: {error}')
        elif request.form.get('clear_image'):
            if recipe.image_path:
                delete_image(recipe.image_path)
            recipe.image_path = None
            recipe.image_url = None
        else:
            image_url = request.form.get('image_url', '').strip()
            if image_url and image_url != recipe.image_url:
                is_valid, error_msg = validate_url(image_url)
                if is_valid:
                    if recipe.image_path:
                        delete_image(recipe.image_path)
                    relative_path, _ = download_image(image_url, recipe_id=recipe.id)
                    if relative_path:
                        recipe.image_path = relative_path
                        recipe.image_url = image_url
                else:
                    current_app.logger.warning(f'Invalid image URL: {error_msg}')
        
        db.session.commit()
        flash('Recipe updated successfully!', 'success')
        return redirect(url_for('main.get_recipe_detail', recipe_id=recipe_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to update recipe: {e}')
        flash('Failed to update recipe. Please try again.', 'error')
        return redirect(url_for('main.edit_recipe_form', recipe_id=recipe_id))


_IMAGE_MAGIC_BYTES = [
    (b'\xff\xd8\xff', None),       # JPEG
    (b'\x89PNG\r\n\x1a\n', None),  # PNG
    (b'GIF87a', None),              # GIF87a
    (b'GIF89a', None),              # GIF89a
    (b'RIFF', b'WEBP'),             # WebP: RIFF????WEBP
]


def _is_valid_image_content(file) -> bool:
    """Check magic bytes to verify the file is a supported image; rewinds the file pointer."""
    header = file.read(12)
    file.seek(0)
    for magic, extra in _IMAGE_MAGIC_BYTES:
        if header[:len(magic)] == magic:
            if extra is not None:
                return header[8:8 + len(extra)] == extra
            return True
    return False


def save_uploaded_image(file, recipe_id):
    """Save an uploaded image file.

    Args:
        file: The uploaded file object
        recipe_id: The recipe ID for filename

    Returns:
        tuple: (relative_path, error_message) - relative_path is None on failure
    """
    # TODO: move uuid and Path imports to module level
    import uuid
    from pathlib import Path

    # SVG excluded: it can contain JavaScript and would be served from our origin.
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    if not file.filename:
        return None, "No file selected"

    # Use only the FINAL suffix to prevent double-extension tricks
    # (e.g. evil.php.jpg → .jpg; evil.jpg.php → .php, which will be rejected)
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        return None, f"Invalid file type. Allowed: {', '.join(sorted(allowed_extensions))}"

    if not _is_valid_image_content(file):
        return None, "File content does not match a supported image format"

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
        tags: Filter by tag names (comma-separated, ALL must match)
        tag_type: Filter by tag type
        tag_names: Filter by tag names (comma-separated, ANY must match)
        difficulty: Filter by difficulty level
        search: Search recipes by title (case-insensitive partial match)
        max_prep_time: Filter by maximum prep time (minutes)
        max_cooking_time: Filter by maximum cooking time (minutes)
        max_total_time: Filter by maximum total time (prep + cooking, works even
                        if only one of prep/cooking is set)
        sort: Sort field — 'title', 'created_at', 'cooking_time', 'difficulty'
              Prefix with '-' for descending (e.g. '-created_at')
        page: Page number for pagination (default: 1)
        per_page: Items per page (default: 20, max: 200)
    
    Returns:
        JSON object with recipes array and pagination info
    """
    # TODO: move func, and_, or_ imports to module level
    from sqlalchemy import func, and_, or_

    # selectinload avoids the row-multiplication that joinedload causes with LIMIT/OFFSET:
    # it issues separate IN-queries after pagination rather than a JOIN before it.
    query = Recipe.query.options(
        selectinload(Recipe.tags),
        selectinload(Recipe.notes)
    )

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE)
    
    # Apply filters if provided
    tag_names_all = request.args.get('tags')     # comma-separated, ALL must match
    tag_names_any = request.args.get('tag_names') # comma-separated, ANY must match
    tag_type = request.args.get('tag_type')
    difficulty = request.args.get('difficulty')
    search_term = request.args.get('search')
    max_prep_time = request.args.get('max_prep_time', type=int)
    max_cooking_time = request.args.get('max_cooking_time', type=int)
    max_total_time = request.args.get('max_total_time', type=int)
    
    # Multi-tag filter — ALL tags must match (intersection)
    if tag_names_all:
        tag_list = [t.strip() for t in tag_names_all.split(',') if t.strip()]
        for t in tag_list:
            query = query.filter(Recipe.tags.any(
                db.func.lower(Tag.name) == db.func.lower(t)
            ))
    
    # Multi-tag filter — ANY tag must match (union)
    if tag_names_any:
        tag_list = [t.strip() for t in tag_names_any.split(',') if t.strip()]
        tag_filters = [
            Recipe.tags.any(db.func.lower(Tag.name) == db.func.lower(t))
            for t in tag_list
        ]
        query = query.filter(or_(*tag_filters))
    
    # Single tag filter (backwards compat)
    # TODO: make this case-insensitive to match the ?tags= and ?tag_names= filters
    tag_name = request.args.get('tag')
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
    
    # Filter by total time — uses whichever is set (prep, cooking, or both)
    if max_total_time is not None:
        total_expr = func.coalesce(Recipe.prep_time, 0) + func.coalesce(Recipe.cooking_time, 0)
        query = query.filter(
            and_(
                db.or_(Recipe.prep_time.isnot(None), Recipe.cooking_time.isnot(None)),
                total_expr <= max_total_time
            )
        )
    
    # Apply sorting
    sort = request.args.get('sort', '-created_at')
    sort_desc = sort.startswith('-')
    sort_field = sort[1:] if sort_desc else sort
    sort_columns = {
        'title': Recipe.title,
        'created_at': Recipe.created_at,
        'cooking_time': Recipe.cooking_time,
        'difficulty': Recipe.difficulty,
    }
    if sort_field in sort_columns:
        col = sort_columns[sort_field]
        query = query.order_by(col.desc() if sort_desc else col.asc())
    
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
@editor_or_admin
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
    recipe = Recipe.query.options(
        joinedload(Recipe.tags),
        joinedload(Recipe.notes)
    ).filter_by(id=recipe_id).first_or_404()
    return jsonify(recipe.to_dict())


@api_bp.route('/recipes/<int:recipe_id>', methods=['PUT'])
@editor_or_admin
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
    recipe = db.get_or_404(Recipe, recipe_id)
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
@admin_required
def delete_recipe(recipe_id):
    """Delete a recipe.

    Also deletes the locally stored cover image if it exists.

    Args:
        recipe_id: Recipe ID

    Returns:
        Empty response with 204 status
    """
    recipe = db.get_or_404(Recipe, recipe_id)
    
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
    count = min(request.args.get('count', 6, type=int), 20)
    return jsonify([r.to_dict() for r in _random_recipes(count)])


# ============================================================================
# Shopping List API Routes
# ============================================================================

@api_bp.route('/shopping-items', methods=['GET'])
def get_shopping_items():
    """Get all shopping list items."""
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
@editor_or_admin
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
            # Normalize: collapse whitespace for consistent comparison
            name = ' '.join(item_data.get('name', '').split())
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
@editor_or_admin
def update_shopping_item(item_id):
    """Update a shopping item."""
    item = db.get_or_404(ShoppingItem, item_id)
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
@admin_required
def delete_shopping_item(item_id):
    """Delete a shopping item."""
    item = db.get_or_404(ShoppingItem, item_id)
    db.session.delete(item)
    db.session.commit()
    return '', 204


@api_bp.route('/shopping-items/clear-purchased', methods=['POST'])
@editor_or_admin
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
    recipe = db.get_or_404(Recipe, recipe_id)
    # Notes are now ordered by created_at.desc() via the relationship
    return jsonify([note.to_dict() for note in recipe.notes])


@api_bp.route('/recipes/<int:recipe_id>/notes', methods=['POST'])
@limiter.limit("30 per minute")
@editor_or_admin
def create_note(recipe_id):
    """Create a new note for a recipe.

    Args:
        recipe_id: Recipe ID

    Request Body (JSON):
        content: (required) Note content

    Returns:
        JSON object of created note with 201 status
    """
    recipe = db.get_or_404(Recipe, recipe_id)
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
@editor_or_admin
def update_note(note_id):
    """Update an existing note.

    Args:
        note_id: Note ID

    Request Body (JSON):
        content: (required) Updated note content

    Returns:
        JSON object of updated note
    """
    note = db.get_or_404(Note, note_id)
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
@admin_required
def delete_note(note_id):
    """Delete a note.

    Args:
        note_id: Note ID

    Returns:
        Empty response with 204 status
    """
    note = db.get_or_404(Note, note_id)
    db.session.delete(note)
    db.session.commit()
    return '', 204


@api_bp.route('/recipes/<int:recipe_id>/tags', methods=['POST'])
@limiter.limit("20 per minute")
@editor_or_admin
def add_recipe_tag(recipe_id):
    """Add a tag to a recipe.

    Args:
        recipe_id: Recipe ID

    Request Body (JSON):
        tag: (required) Tag name

    Returns:
        JSON object of the added tag with 201 status
    """
    recipe = db.get_or_404(Recipe, recipe_id)
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

