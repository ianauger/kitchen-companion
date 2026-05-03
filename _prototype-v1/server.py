#!/usr/bin/env python3
"""Kitchen Companion API Server — lightweight Flask backend."""

import json
import os
import urllib.request
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

DB_PATH = os.path.join(os.path.dirname(__file__), 'recipes', 'database.json')
IMAGES_DIR = os.path.join(os.path.dirname(__file__), 'recipes', 'images')


def load_db():
    with open(DB_PATH, 'r') as f:
        return json.load(f)


def save_db(data):
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_images_dir():
    os.makedirs(IMAGES_DIR, exist_ok=True)


def download_image(url, filename):
    """Download image from URL to local images directory."""
    ensure_images_dir()
    filepath = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(filepath):
        return filename
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'KitchenCompanion/1.0'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(filepath, 'wb') as f:
                f.write(resp.read())
        print(f"  ✓ Downloaded: {filename}")
        return filename
    except Exception as e:
        print(f"  ✗ Failed to download {url}: {e}")
        return None


# ─── Static file serving ───

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/recipes/<path:filename>')
def recipe_files(filename):
    return send_from_directory('recipes', filename)


# ─── API endpoints ───

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    """Return all recipes (both core and showcase)."""
    db = load_db()
    return jsonify(db)


@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    """Add a new showcase recipe with full details including image."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body provided'}), 400

    # Validate required fields
    required = ['title', 'ingredients', 'instructions']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400

    db = load_db()

    # Build the recipe entry
    recipe_uid = data.get('recipe_uid') or f"showcase-{uuid.uuid4().hex[:8]}"
    
    # Process ingredients — accept both string list and object list
    ingredients = data.get('ingredients', [])
    processed_ingredients = []
    for ing in ingredients:
        if isinstance(ing, str):
            # Parse "2 cups flour" → quantity + item
            parts = ing.split(None, 1)
            if len(parts) == 2:
                processed_ingredients.append({'item': parts[1], 'quantity': parts[0]})
            else:
                processed_ingredients.append({'item': ing, 'quantity': ''})
        elif isinstance(ing, dict):
            processed_ingredients.append(ing)
    
    # Process instructions — accept both string list and numbered string
    instructions = data.get('instructions', [])
    if isinstance(instructions, str):
        instructions = [s.strip() for s in instructions.split('\n') if s.strip()]

    # Download image if URL provided
    image_url = data.get('image_url', '')
    local_image = None
    if image_url:
        ext = image_url.rsplit('.', 1)[-1].split('?')[0] if '.' in image_url else 'jpg'
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
            ext = 'jpg'
        filename = f"{recipe_uid}.{ext}"
        local_image = download_image(image_url, filename)

    # Build entry
    entry = {
        'recipe_uid': recipe_uid,
        'recipe_name': data.get('title', data.get('recipe_name', 'Untitled')),
        'title': data.get('title', data.get('recipe_name', 'Untitled')),
        'base': data.get('base', data.get('tags', {}).get('cuisine', 'Unknown') if isinstance(data.get('tags'), dict) else 'Unknown'),
        'protein': data.get('protein', data.get('tags', {}).get('protein', 'Mixed') if isinstance(data.get('tags'), dict) else 'Mixed'),
        'pivot': data.get('pivot', data.get('tags', {}).get('cuisine', 'Fusion') if isinstance(data.get('tags'), dict) else 'Fusion'),
        'ingredients': processed_ingredients,
        'steps': instructions if isinstance(instructions, list) else [instructions],
        'instructions': instructions if isinstance(instructions, list) else [instructions],
        'estimated_cost_per_serving': data.get('estimated_cost_per_serving', 0),
        'calories_est': data.get('calories_est', 0),
        'servings': data.get('servings', 4),
        'cooking_time': data.get('cooking_time', ''),
        'prep_time': data.get('prep_time', ''),
        'tags': data.get('tags', {}),
        'image_url': image_url,
        'local_image': f"/recipes/images/{local_image}" if local_image else None,
        'spice_level': data.get('tags', {}).get('spice_level', 'mild') if isinstance(data.get('tags'), dict) else 'mild',
        'added_date': datetime.now().strftime('%Y-%m-%d'),
        'source': data.get('source', 'showcase'),
    }

    # Add to showcase_recipes array in DB
    if 'showcase_recipes' not in db:
        db['showcase_recipes'] = []
    
    db['showcase_recipes'].append(entry)
    save_db(db)

    print(f"  ✓ Added recipe: {entry['recipe_name']} (UID: {recipe_uid})")
    return jsonify({'status': 'ok', 'recipe_uid': recipe_uid, 'entry': entry}), 201


@app.route('/api/recipes/<recipe_uid>', methods=['GET'])
def get_recipe(recipe_uid):
    """Get a single recipe by UID."""
    db = load_db()
    for recipe_list in ['recipes', 'external_recipes', 'showcase_recipes']:
        for r in db.get(recipe_list, []):
            if r.get('recipe_uid') == recipe_uid or r.get('recipe_name', '').lower().replace(' ', '-') == recipe_uid:
                return jsonify(r)
    return jsonify({'error': 'Recipe not found'}), 404


if __name__ == '__main__':
    ensure_images_dir()
    print("🍳 Kitchen Companion API Server starting on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)