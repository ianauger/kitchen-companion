"""Route handlers for Kitchen Companion application."""
from flask import Blueprint, request, jsonify, render_template, url_for
from app import db
from app.models import Recipe, Tag
from app.image_utils import download_image, delete_image, validate_url

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
    # Use database-level random sampling for efficiency
    from sqlalchemy import func
    recipes_list = Recipe.query.order_by(func.random()).limit(6).all()
    return render_template('home.html', recipes=recipes_list)


@main_bp.route('/recipe/<int:recipe_id>')
def get_recipe_detail(recipe_id):
    """Render the detailed view of a single recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
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


@main_bp.route('/features')
def features():
    """Render the features page."""
    return render_template('features.html')


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
    
    Returns:
        JSON array of recipes
    """
    from sqlalchemy import func, and_
    
    query = Recipe.query
    
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
    
    recipes = query.all()
    return jsonify([recipe.to_dict() for recipe in recipes])


@api_bp.route('/recipes', methods=['POST'])
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
            tag, _ = Tag.get_or_create(
                name=tag_data['name'],
                tag_type=tag_data.get('tag_type', 'custom')
            )
            recipe.tags.append(tag)
    
    db.session.add(recipe)
    db.session.flush()  # Get the recipe ID before downloading image
    
    # Download image if URL provided
    if image_url:
        relative_path, _ = download_image(image_url, recipe_id=recipe.id)
        if relative_path:
            recipe.image_path = relative_path
            recipe.image_url = image_url
    
    db.session.commit()
    
    return jsonify(recipe.to_dict()), 201


@api_bp.route('/recipes/<int:recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    """Get a specific recipe by ID.
    
    Args:
        recipe_id: Recipe ID
    
    Returns:
        JSON object of the recipe or 404 error
    """
    recipe = Recipe.query.get_or_404(recipe_id)
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
            tag, _ = Tag.get_or_create(
                name=tag_data['name'],
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
    # Use database-level random sampling
    recipes = Recipe.query.order_by(func.random()).limit(count).all()
    return jsonify([recipe.to_dict() for recipe in recipes])


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint.
    
    Returns:
        JSON status object
    """
    return jsonify({'status': 'healthy'})
