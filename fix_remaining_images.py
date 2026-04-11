#!/usr/bin/env python3
"""Fix missing images for recipes 11, 13, and 18."""
import os
import sqlite3
import requests
import uuid

DB_PATH = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/kitchen_companion.db'
UPLOAD_DIR = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/app/static/uploads/recipes'

def download_image(url, recipe_id):
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

# New image URLs for recipes with missing local images
fixes = {
    11: 'https://images.unsplash.com/photo-1525755662778-989d0524087d?w=800&q=80',
    13: 'https://images.unsplash.com/photo-1583224964978-2257b960c3d3?w=800&q=80',
    18: 'https://images.unsplash.com/photo-1601058282534-62f9e0e3a8a9?w=800&q=80',
}

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

for recipe_id, new_url in fixes.items():
    cursor.execute('SELECT id, title, image_path FROM recipes WHERE id = ?', (recipe_id,))
    row = cursor.fetchone()
    if row:
        print(f'Recipe {row[0]}: {row[1]}')
        print(f'  Current image_path: {row[2]}')
    
    print(f'  Attempting download...')
    relative_path = download_image(new_url, recipe_id)
    
    if relative_path:
        cursor.execute('UPDATE recipes SET image_url = ?, image_path = ? WHERE id = ?',
                       (new_url, relative_path, recipe_id))
        print(f'  Updated: image_path = {relative_path}')
    else:
        cursor.execute('UPDATE recipes SET image_url = ? WHERE id = ?', (new_url, recipe_id))
        print(f'  Updated image_url only (will use remote fallback)')

conn.commit()

# Final verification
cursor.execute('SELECT id, title, image_path FROM recipes ORDER BY id')
print('\n=== Final Status ===')
for row in cursor.fetchall():
    status = '✅' if row[2] else '❌ remote only'
    print(f'  {row[0]:2d}. {row[1][:45]:<45} {status}')

conn.close()