"""Route handlers for Kitchen Companion application."""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import (Recipe, Tag, Note, ShoppingItem,
                         Store, StoreAisle, AisleOverride, MealPlan,
                         PrepSession, PrepSessionRecipe, PrepTask,
                         classify_aisle, seed_default_store)
from app.auth import editor_or_admin, admin_required, login_required_web, editor_or_admin_web
from app.image_utils import download_image, delete_image, validate_url, get_upload_dir
from app.prep_analyzer import PrepAnalyzer
from config import (
    MAX_NOTE_LENGTH, MAX_TAG_NAME_LENGTH,
    DEFAULT_PER_PAGE, MAX_PER_PAGE
)
from sqlalchemy.orm import joinedload, selectinload
import os
import random
from datetime import datetime, timezone, date, timedelta

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


def _normalize_item_name(name):
    """Return a normalized version of an item name for override lookups."""
    return name.strip().lower() if name else ''


def _resolve_aisle_for_item(item_name, store_id):
    """Determine the best aisle for an item in a given store.

    Priority:
    1. AisleOverride for this item name + store
    2. classify_aisle() keyword matching
    Returns (aisle_name, override_id_or_None).
    """
    normalized = _normalize_item_name(item_name)
    if normalized and store_id:
        override = AisleOverride.query.filter_by(
            store_id=store_id,
            item_name_normalized=normalized
        ).first()
        if override and override.aisle_rel:
            return override.aisle_rel.name, override.id

    return classify_aisle(item_name), None


def _iso_week_to_date_range(iso_week_str):
    """Convert an ISO week string (e.g. '2026-W20') to (start_date, end_date).

    Weeks start on Monday per ISO 8601.
    """
    try:
        year, week = iso_week_str.split('-W')
        year, week = int(year), int(week)
    except (ValueError, TypeError):
        return _current_iso_week_range()

    # Find the Monday of that ISO week
    jan4 = date(year, 1, 4)
    # Monday of week containing Jan 4
    monday = jan4 - timedelta(days=jan4.weekday())
    target_monday = monday + timedelta(weeks=week - 1)
    return target_monday, target_monday + timedelta(days=6)


def _current_iso_week_range():
    """Return (monday, sunday) for the current ISO week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def _current_iso_week():
    """Return the current ISO week string (e.g. '2026-W20')."""
    today = date.today()
    iso = today.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _next_iso_week(iso_week_str):
    """Return the next ISO week string."""
    start, _ = _iso_week_to_date_range(iso_week_str)
    nxt = start + timedelta(weeks=1)
    iso = nxt.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _prev_iso_week(iso_week_str):
    """Return the previous ISO week string."""
    start, _ = _iso_week_to_date_range(iso_week_str)
    prv = start - timedelta(weeks=1)
    iso = prv.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


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
    # Pass all stores for the store selector
    stores = Store.query.order_by(Store.name).all()
    default_store = Store.query.filter_by(name='Default').first()
    return render_template('shopping_list.html',
                           stores=stores,
                           default_store_id=default_store.id if default_store else None)


@main_bp.route('/meal-plan')
def meal_plan_page():
    """Render the meal plan calendar page."""
    return render_template('meal_plan.html')


# ============================================================================
# Prep Session Routes
# ============================================================================

@main_bp.route('/prep')
def prep_index():
    """Render the prep session list page."""
    sessions = PrepSession.query.order_by(PrepSession.updated_at.desc()).all()
    return render_template('prep_index.html', sessions=sessions)


@main_bp.route('/prep/sessions', methods=['POST'])
@editor_or_admin_web
def create_prep_session():
    """Create a new prep session.

    Expects JSON: { name (optional), recipe_ids: [1, 2, 3] }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    recipe_ids = data.get('recipe_ids', [])
    if not recipe_ids or not isinstance(recipe_ids, list):
        return jsonify({'error': 'recipe_ids array is required'}), 400

    session_name = data.get('name', '').strip() or None

    # Verify all recipes exist
    recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
    if len(recipes) != len(recipe_ids):
        return jsonify({'error': 'One or more recipe IDs are invalid'}), 400

    session = PrepSession(name=session_name)
    db.session.add(session)
    db.session.flush()

    for idx, rid in enumerate(recipe_ids):
        psr = PrepSessionRecipe(
            session_id=session.id,
            recipe_id=rid,
            sort_order=idx,
        )
        db.session.add(psr)

    db.session.commit()
    return jsonify(session.to_dict(include_analysis=True)), 201


@main_bp.route('/prep/sessions/<int:session_id>')
def get_prep_session(session_id):
    """Get session detail with analysis, rendered as HTML."""
    session = PrepSession.query.filter_by(id=session_id).first_or_404()
    return render_template('prep_detail.html', session=session)


@main_bp.route('/prep/sessions/<int:session_id>', methods=['PUT'])
@editor_or_admin_web
def update_prep_session(session_id):
    """Update session name or recipe list.

    Expects JSON: { name (optional), recipe_ids: [1, 2, 3] (optional) }
    """
    session = PrepSession.query.filter_by(id=session_id).first_or_404()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        session.name = data['name'].strip() or None

    if 'recipe_ids' in data:
        recipe_ids = data['recipe_ids']
        if not isinstance(recipe_ids, list):
            return jsonify({'error': 'recipe_ids must be an array'}), 400

        # Verify recipes exist
        recipes = Recipe.query.filter(Recipe.id.in_(recipe_ids)).all()
        if len(recipes) != len(recipe_ids):
            return jsonify({'error': 'One or more recipe IDs are invalid'}), 400

        # Remove existing and replace
        PrepSessionRecipe.query.filter_by(session_id=session.id).delete()
        for idx, rid in enumerate(recipe_ids):
            psr = PrepSessionRecipe(
                session_id=session.id,
                recipe_id=rid,
                sort_order=idx,
            )
            db.session.add(psr)

        # Clear old analysis tasks when recipes change
        PrepTask.query.filter_by(session_id=session.id).delete()

    db.session.commit()
    return jsonify(session.to_dict(include_analysis=True))


@main_bp.route('/prep/sessions/<int:session_id>', methods=['DELETE'])
@admin_required
def delete_prep_session(session_id):
    """Delete a prep session and all related records."""
    session = PrepSession.query.filter_by(id=session_id).first_or_404()
    db.session.delete(session)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


@main_bp.route('/prep/sessions/<int:session_id>/analyze', methods=['POST'])
@editor_or_admin_web
def analyze_prep_session(session_id):
    """Trigger analysis — generates PrepTasks from combined recipes."""
    session = PrepSession.query.filter_by(id=session_id).first_or_404()

    # Gather all recipes in this session
    recipes = [psr.recipe for psr in session.recipes if psr.recipe]
    if not recipes:
        return jsonify({'error': 'No recipes in session'}), 400

    # Clear old tasks
    PrepTask.query.filter_by(session_id=session.id).delete()
    db.session.flush()

    # Run analysis
    analyzer = PrepAnalyzer(recipes)
    timeline = analyzer.generate_timeline()

    # Create PrepTask records from timeline
    for idx, task_data in enumerate(timeline['tasks']):
        prep_task = PrepTask(
            session_id=session.id,
            description=task_data['description'],
            category=task_data['category'],
            recipe_id=task_data.get('recipe_id'),
            estimated_minutes=task_data.get('estimated_minutes'),
            sort_order=idx,
            is_parallel=task_data.get('is_parallel', False),
        )
        db.session.add(prep_task)
        db.session.flush()

        # Store depends_on after all tasks are created
        task_data['_db_id'] = prep_task.id

    # Now set depends_on links (simplified: link sequential tasks within
    # each recipe by step_index)
    recipe_task_order = {}
    for task_data in timeline['tasks']:
        rid = task_data.get('recipe_id')
        si = task_data.get('step_index', 0)
        if rid not in recipe_task_order:
            recipe_task_order[rid] = []
        recipe_task_order[rid].append((si, task_data['_db_id']))

    for rid, ordered in recipe_task_order.items():
        ordered.sort(key=lambda x: x[0])
        for i in range(1, len(ordered)):
            prev_db_id = ordered[i - 1][1]
            curr_db_id = ordered[i][1]
            curr_task = PrepTask.query.get(curr_db_id)
            if curr_task:
                curr_task.depends_on = prev_db_id

    db.session.commit()

    # Build response
    result = session.to_dict(include_analysis=True)
    result['timeline'] = {
        'total_time': timeline['total_time'],
        'parallel_windows': timeline['parallel_windows'],
    }
    return jsonify(result)


@main_bp.route('/prep/tasks/<int:task_id>', methods=['PUT'])
@editor_or_admin_web
def update_prep_task(task_id):
    """Toggle task completion or reorder.

    Expects JSON: { completed (optional), sort_order (optional) }
    """
    task = PrepTask.query.filter_by(id=task_id).first_or_404()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'completed' in data:
        task.completed = bool(data['completed'])
    if 'sort_order' in data:
        task.sort_order = int(data['sort_order'])

    db.session.commit()
    return jsonify(task.to_dict())


@main_bp.route('/prep/sessions/<int:session_id>/ingredients')
def get_prep_ingredients(session_id):
    """Get combined, deduplicated ingredient list grouped by category.

    Returns JSON:
        { "categories": [...], "shared": {...}, "session": {...} }
    """
    session = PrepSession.query.filter_by(id=session_id).first_or_404()
    recipes = [psr.recipe for psr in session.recipes if psr.recipe]

    if not recipes:
        return jsonify({
            'categories': [],
            'shared': {},
            'session': session.to_dict(),
        })

    analyzer = PrepAnalyzer(recipes)
    ingredients = analyzer.get_combined_ingredients()
    ingredients['session'] = session.to_dict()
    return jsonify(ingredients)


@main_bp.route('/prep/sessions/<int:session_id>/timeline')
def get_prep_timeline(session_id):
    """Get prep timeline as JSON.

    Returns:
        { total_time, tasks: [...], parallel_windows: [...] }
    """
    session = PrepSession.query.filter_by(id=session_id).first_or_404()
    tasks = PrepTask.query.filter_by(session_id=session_id).order_by(
        PrepTask.sort_order
    ).all()

    tasks_data = [t.to_dict() for t in tasks]

    # Calculate total time and parallel windows from saved tasks
    active_total = 0
    parallel_times = []
    parallel_windows = []
    for t in tasks:
        if t.estimated_minutes:
            if t.is_parallel:
                parallel_times.append(t.estimated_minutes)
                parallel_windows.append({
                    'task_id': t.id,
                    'task_description': t.description,
                    'duration': t.estimated_minutes,
                    'hint': f'"{t.description[:50]}..." can happen while active tasks proceed',
                })
            else:
                active_total += t.estimated_minutes

    longest_parallel = max(parallel_times) if parallel_times else 0
    total_time = active_total + longest_parallel

    return jsonify({
        'total_time': total_time if total_time > 0 else None,
        'tasks': tasks_data,
        'parallel_windows': parallel_windows,
        'session_name': session.name,
    })


# ============================================================================
# Store Routes
# ============================================================================

@main_bp.route('/stores', methods=['GET'])
def get_stores():
    """Get all stores with aisle counts."""
    stores = Store.query.order_by(Store.name).all()
    return jsonify([s.to_dict() for s in stores])


@main_bp.route('/stores', methods=['POST'])
@editor_or_admin_web
def create_store():
    """Create a new store, copying the Default store's aisle list."""
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': 'Store name is required'}), 400

    store = Store(name=data['name'].strip())
    db.session.add(store)
    db.session.flush()

    # Copy aisles from Default store
    default = Store.query.filter_by(name='Default').first()
    if default:
        for aisle in default.aisles:
            sa = StoreAisle(
                store_id=store.id,
                name=aisle.name,
                sort_order=aisle.sort_order
            )
            db.session.add(sa)
    else:
        # Fallback: create default aisles
        for i, name in enumerate([
            'Produce', 'Meat & Seafood', 'Deli', 'Dairy', 'Bakery',
            'Grains & Pasta', 'Canned Goods', 'Spices', 'Condiments & Sauces',
            'Frozen', 'Beverages', 'International', 'Health & Beauty',
            'Household', 'Other'
        ]):
            sa = StoreAisle(store_id=store.id, name=name, sort_order=i)
            db.session.add(sa)

    db.session.commit()
    return jsonify(store.to_dict(include_aisles=True)), 201


@main_bp.route('/stores/<int:store_id>', methods=['PUT'])
@editor_or_admin_web
def update_store(store_id):
    """Rename a store."""
    store = db.get_or_404(Store, store_id)
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': 'Store name is required'}), 400
    store.name = data['name'].strip()
    db.session.commit()
    return jsonify(store.to_dict())


@main_bp.route('/stores/<int:store_id>/aisles', methods=['PUT'])
@editor_or_admin_web
def update_store_aisles(store_id):
    """Update aisles for a store — reorder or rename.

    Expects JSON: { "aisles": [{"id": 1, "name": "Produce", "sort_order": 0}, ...] }
    """
    store = db.get_or_404(Store, store_id)
    data = request.get_json()
    if not data or 'aisles' not in data:
        return jsonify({'error': 'aisles array is required'}), 400

    existing_ids = {a.id for a in store.aisles}
    submitted_ids = set()

    for a_data in data['aisles']:
        aid = a_data.get('id')
        if aid:
            submitted_ids.add(aid)
            aisle = StoreAisle.query.filter_by(id=aid, store_id=store_id).first()
            if aisle:
                if 'name' in a_data and a_data['name'].strip():
                    aisle.name = a_data['name'].strip()
                if 'sort_order' in a_data:
                    aisle.sort_order = int(a_data['sort_order'])

    # Delete aisles not in the submitted list
    to_delete = existing_ids - submitted_ids
    if to_delete:
        StoreAisle.query.filter(
            StoreAisle.id.in_(to_delete),
            StoreAisle.store_id == store_id
        ).delete(synchronize_session='fetch')

    db.session.commit()
    return jsonify(store.to_dict(include_aisles=True))


@main_bp.route('/aisles', methods=['GET'])
def get_aisles():
    """Get aisles for a store, ordered by sort_order.

    Query: ?store_id=X
    """
    store_id = request.args.get('store_id', type=int)
    if not store_id:
        return jsonify({'error': 'store_id is required'}), 400
    store = db.get_or_404(Store, store_id)
    return jsonify([a.to_dict() for a in store.aisles])


# ============================================================================
# Aisle Override Routes
# ============================================================================

@main_bp.route('/stores/<int:store_id>/overrides', methods=['GET'])
def get_store_overrides(store_id):
    """Export all overrides for a store as JSON."""
    store = db.get_or_404(Store, store_id)
    overrides = AisleOverride.query.filter_by(store_id=store_id).all()
    return jsonify([o.to_dict() for o in overrides])


@main_bp.route('/stores/<int:store_id>/overrides', methods=['POST'])
@editor_or_admin_web
def import_store_overrides(store_id):
    """Import overrides from JSON.

    Expects: { "overrides": [{"item_name_normalized": "chicken", "aisle_name": "Meat & Seafood"}, ...] }

    Creates or updates overrides.  If an aisle_name doesn't exist,
    it is created at the end of the aisle list.
    """
    store = db.get_or_404(Store, store_id)
    data = request.get_json()
    if not data or 'overrides' not in data:
        return jsonify({'error': 'overrides array is required'}), 400

    created = 0
    updated = 0
    for ov_data in data['overrides']:
        item_name = _normalize_item_name(ov_data.get('item_name_normalized', ''))
        aisle_name = ov_data.get('aisle_name', '').strip()
        if not item_name or not aisle_name:
            continue

        # Find or create the aisle
        aisle = StoreAisle.query.filter_by(
            store_id=store_id, name=aisle_name
        ).first()
        if not aisle:
            max_order = db.session.query(
                db.func.max(StoreAisle.sort_order)
            ).filter_by(store_id=store_id).scalar() or -1
            aisle = StoreAisle(
                store_id=store_id, name=aisle_name,
                sort_order=max_order + 1
            )
            db.session.add(aisle)
            db.session.flush()

        existing = AisleOverride.query.filter_by(
            store_id=store_id, item_name_normalized=item_name
        ).first()
        if existing:
            existing.aisle_id = aisle.id
            updated += 1
        else:
            ov = AisleOverride(
                store_id=store_id,
                item_name_normalized=item_name,
                aisle_id=aisle.id
            )
            db.session.add(ov)
            created += 1

    db.session.commit()
    # Refresh store aisles after potential adds
    store_aisles = StoreAisle.query.filter_by(store_id=store_id).order_by(
        StoreAisle.sort_order
    ).all()
    return jsonify({
        'created': created,
        'updated': updated,
        'aisles': [a.to_dict() for a in store_aisles]
    }), 200


# ============================================================================
# Shopping List Web UI Routes (session-based auth)
# ============================================================================

@main_bp.route('/shopping-items', methods=['GET'])
def get_shopping_items_web():
    """Get all shopping list items grouped by store aisles.

    Query: ?store_id=X — group by that store's aisle order.
    Items without a matching aisle go to 'Other'.
    """
    store_id = request.args.get('store_id', type=int)
    items = ShoppingItem.query.options(
        joinedload(ShoppingItem.recipe),
        joinedload(ShoppingItem.aisle_override)
    ).order_by(
        ShoppingItem.purchased.asc(),
        ShoppingItem.created_at.desc()
    ).all()

    if store_id:
        store = db.get_or_404(Store, store_id)
        aisles = {a.name: a for a in store.aisles}
        # Build grouped structure
        groups = {}
        for aisle in store.aisles:
            groups[aisle.name] = {'id': aisle.id, 'name': aisle.name, 'items': []}
        groups['Other'] = {'id': None, 'name': 'Other', 'items': []}

        for item in items:
            # Determine what aisle this item belongs to
            aisle_name = classify_aisle(item.name)
            override_aisle_id = None

            # Check for an explicit override
            normalized = _normalize_item_name(item.name)
            if normalized:
                override = AisleOverride.query.filter_by(
                    store_id=store_id, item_name_normalized=normalized
                ).first()
                if override and override.aisle_rel:
                    aisle_name = override.aisle_rel.name
                    override_aisle_id = override.id

            # Find the aisle in our groups
            if aisle_name in groups:
                item_dict = item.to_dict()
                item_dict['aisle_name'] = aisle_name
                item_dict['override_aisle_id'] = override_aisle_id
                groups[aisle_name]['items'].append(item_dict)
            else:
                item_dict = item.to_dict()
                item_dict['aisle_name'] = 'Other'
                item_dict['override_aisle_id'] = override_aisle_id
                groups['Other']['items'].append(item_dict)

        # Build ordered result
        result_aisles = []
        for aisle in store.aisles:
            name = aisle.name
            if name in groups and groups[name]['items']:
                result_aisles.append(groups[name])
        # Append Other only if it has items
        if groups['Other']['items']:
            result_aisles.append(groups['Other'])

        return jsonify({
            'aisles': result_aisles,
            'store': store.to_dict()
        })
    else:
        # No store — return flat list
        return jsonify([item.to_dict() for item in items])


@main_bp.route('/shopping-items', methods=['POST'])
@limiter.limit("30 per minute")
@editor_or_admin_web
def add_shopping_items_web():
    """Add items to the shopping list (web UI, session auth).

    Accepts optional store_id param for auto-classification.
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'items array is required'}), 400
    if not isinstance(data['items'], list):
        return jsonify({'error': 'items must be an array'}), 400

    store_id = data.get('store_id')
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

            # Auto-classify aisle
            aisle_name, override_id = _resolve_aisle_for_item(name, store_id)

            item = ShoppingItem(
                name=name,
                recipe_id=ri if ri else None,
                aisle_override_id=override_id
            )
            db.session.add(item)
            db.session.flush()
            item_dict = item.to_dict()
            item_dict['aisle_name'] = aisle_name
            added.append(item_dict)

        db.session.commit()
        return jsonify({'items': added, 'count': len(added)}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to add shopping items (web): {e}')
        return jsonify({'error': 'Failed to add items'}), 500


@main_bp.route('/shopping-items/<int:item_id>', methods=['PUT'])
@editor_or_admin_web
def update_shopping_item_web(item_id):
    """Update a shopping item (web UI, session auth).

    If aisle_id is changed and differs from auto-classified,
    creates/updates an AisleOverride.
    """
    item = db.get_or_404(ShoppingItem, item_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'purchased' in data:
        item.purchased = bool(data['purchased'])
    if 'name' in data and data['name'].strip():
        item.name = data['name'].strip()

    # Handle aisle assignment
    if 'aisle_id' in data and data.get('store_id'):
        store_id = data['store_id']
        new_aisle_id = data['aisle_id']

        # Get the aisle name for the new assignment
        new_aisle = StoreAisle.query.filter_by(
            id=new_aisle_id, store_id=store_id
        ).first()

        if new_aisle:
            # Check what auto-classification would give
            auto_aisle_name = classify_aisle(item.name)
            normalized = _normalize_item_name(item.name)
            existing_override = AisleOverride.query.filter_by(
                store_id=store_id, item_name_normalized=normalized
            ).first()

            if new_aisle.name != auto_aisle_name:
                # Manual override: create or update
                if existing_override:
                    existing_override.aisle_id = new_aisle_id
                elif normalized:
                    ov = AisleOverride(
                        store_id=store_id,
                        item_name_normalized=normalized,
                        aisle_id=new_aisle_id
                    )
                    db.session.add(ov)
                    db.session.flush()
                    item.aisle_override_id = ov.id
            elif existing_override:
                # Reverted to auto-classified — remove override
                db.session.delete(existing_override)
                item.aisle_override_id = None

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
# Meal Plan Routes
# ============================================================================

@main_bp.route('/meal-plan/data', methods=['GET'])
def get_meal_plan():
    """Get a full week meal plan.

    Query: ?week=2026-W20 — ISO week (defaults to current week).
    """
    week_str = request.args.get('week', _current_iso_week())
    start_date, end_date = _iso_week_to_date_range(week_str)

    # Query all meal plans for this date range
    plans = MealPlan.query.options(
        joinedload(MealPlan.recipe)
    ).filter(
        MealPlan.date >= start_date,
        MealPlan.date <= end_date
    ).order_by(MealPlan.date.asc(), MealPlan.meal_type.asc()).all()

    # Build plan_by_date structure
    plan_by_date = {}
    d = start_date
    while d <= end_date:
        date_key = d.isoformat()
        plan_by_date[date_key] = {}
        d += timedelta(days=1)

    for mp in plans:
        date_key = mp.date.isoformat()
        plan_by_date[date_key][mp.meal_type] = mp.to_dict()

    return jsonify({
        'plan_by_date': plan_by_date,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'current_week': _current_iso_week(),
        'this_week': week_str,
        'next_week': _next_iso_week(week_str),
        'prev_week': _prev_iso_week(week_str),
    })


@main_bp.route('/meal-plan', methods=['POST'])
@editor_or_admin_web
def upsert_meal_plan():
    """Create or update a meal plan entry.

    Expects JSON: { date, meal_type, recipe_id(optional), notes(optional) }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if 'date' not in data or 'meal_type' not in data:
        return jsonify({'error': 'date and meal_type are required'}), 400

    meal_type = data['meal_type']
    if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
        return jsonify({'error': 'Invalid meal_type'}), 400

    try:
        plan_date = date.fromisoformat(data['date'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400

    # Find existing or create new
    mp = MealPlan.query.filter_by(
        date=plan_date, meal_type=meal_type
    ).first()

    if mp is None:
        mp = MealPlan(date=plan_date, meal_type=meal_type)
        db.session.add(mp)

    mp.recipe_id = data.get('recipe_id')
    mp.notes = data.get('notes')
    db.session.commit()

    return jsonify(mp.to_dict()), 200 if mp else 201


@main_bp.route('/meal-plan/<int:mp_id>', methods=['DELETE'])
@editor_or_admin_web
def delete_meal_plan(mp_id):
    """Remove a meal plan entry."""
    mp = db.get_or_404(MealPlan, mp_id)
    db.session.delete(mp)
    db.session.commit()
    return '', 204


@main_bp.route('/recipes/simple', methods=['GET'])
def get_recipes_simple():
    """Get simplified recipe list for dropdowns.

    Returns: [{id, title}] — no ingredients/instructions.
    """
    recipes = Recipe.query.order_by(Recipe.title).all()
    return jsonify([{'id': r.id, 'title': r.title} for r in recipes])


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

    store_id = data.get('store_id')
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

            aisle_name, override_id = _resolve_aisle_for_item(name, store_id)
            item = ShoppingItem(
                name=name,
                recipe_id=ri if ri else None,
                aisle_override_id=override_id
            )
            db.session.add(item)
            db.session.flush()
            item_dict = item.to_dict()
            item_dict['aisle_name'] = aisle_name
            added.append(item_dict)

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

    if 'aisle_id' in data and data.get('store_id'):
        store_id = data['store_id']
        new_aisle_id = data['aisle_id']
        new_aisle = StoreAisle.query.filter_by(id=new_aisle_id, store_id=store_id).first()
        if new_aisle:
            auto_aisle_name = classify_aisle(item.name)
            normalized = _normalize_item_name(item.name)
            existing_override = AisleOverride.query.filter_by(
                store_id=store_id, item_name_normalized=normalized
            ).first()
            if new_aisle.name != auto_aisle_name:
                if existing_override:

                    existing_override.aisle_id = new_aisle_id
                elif normalized:
                    ov = AisleOverride(store_id=store_id, item_name_normalized=normalized, aisle_id=new_aisle_id)
                    db.session.add(ov)
                    db.session.flush()
                    item.aisle_override_id = ov.id
            elif existing_override:
                db.session.delete(existing_override)
                item.aisle_override_id = None

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
