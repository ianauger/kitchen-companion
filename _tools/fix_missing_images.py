#!/usr/bin/env python3
"""Fix missing images for recipes 1 and 9 by downloading directly."""
import os
import sys
import sqlite3
import requests
import uuid

DB_PATH = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/kitchen_companion.db'
UPLOAD_DIR = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/app/static/uploads/recipes'

def download_image(url, recipe_id):
    """Download image and return relative path."""
    try:
        resp = requests.get(url, timeout=15, stream=True)
        resp.raise_for_status()
        ext = '.jpg'
        filename = f'recipe_{recipe_id}_{uuid.uuid4().hex[:8]}{ext}'
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        relative_path = f'uploads/recipes/{filename}'
        print(f'  Downloaded: {filepath} ({os.path.getsize(filepath)} bytes)')
        return relative_path
    except Exception as e:
        print(f'  Download failed: {e}')
        return None

# New image URLs for the two missing recipes
fixes = {
    1: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=80',
    9: 'https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=800&q=80',
}

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

for recipe_id, new_url in fixes.items():
    cursor.execute('SELECT id, title, image_url, image_path FROM recipe WHERE id = ?', (recipe_id,))
    row = cursor.fetchone()
    if row:
        print(f'Recipe {row[0]}: {row[1]}')
        print(f'  Current image_url: {row[2][:60] if row[2] else "None"}...')
        print(f'  Current image_path: {row[3]}')
    
    # Try downloading the new image
    print(f'  Attempting download from: {new_url[:60]}...')
    relative_path = download_image(new_url, recipe_id)
    
    if relative_path:
        cursor.execute('UPDATE recipe SET image_url = ?, image_path = ? WHERE id = ?',
                       (new_url, relative_path, recipe_id))
        print(f'  Updated: image_path = {relative_path}')
    else:
        # Just update the URL, the template will fall back to remote
        cursor.execute('UPDATE recipe SET image_url = ? WHERE id = ?', (new_url, recipe_id))
        print(f'  Updated image_url only (no local download)')

conn.commit()

# Verify all recipes
cursor.execute('SELECT id, title, image_path, image_url FROM recipe ORDER BY id')
print('\n=== Final Status ===')
for row in cursor.fetchall():
    has_img = '✅' if row[2] else '❌ (remote fallback)'
    print(f'  {row[0]:2d}. {row[1][:40]:<40} {has_img}')

conn.close()