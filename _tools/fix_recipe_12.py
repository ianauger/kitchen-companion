#!/usr/bin/env python3
"""Fix missing image for recipe 12."""
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

url = 'https://images.unsplash.com/photo-1581781870029-2a68b3c4c99e?w=800&q=80'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('Recipe 12: Japanese Chicken Katsu Curry')
relative_path = download_image(url, 12)

if relative_path:
    cursor.execute('UPDATE recipes SET image_url = ?, image_path = ? WHERE id = 12', (url, relative_path))
    print(f'  Updated: image_path = {relative_path}')
else:
    # Try another URL
    url2 = 'https://images.unsplash.com/photo-1619963890846-e557fa4b9072?w=800&q=80'
    print(f'  Trying fallback URL...')
    relative_path = download_image(url2, 12)
    if relative_path:
        cursor.execute('UPDATE recipes SET image_url = ?, image_path = ? WHERE id = 12', (url2, relative_path))
        print(f'  Updated: image_path = {relative_path}')
    else:
        cursor.execute('UPDATE recipes SET image_url = ? WHERE id = 12', (url2,))

conn.commit()

# Final check
cursor.execute('SELECT id, title, image_path FROM recipes WHERE id = 12')
row = cursor.fetchone()
status = '✅' if row[2] else '❌ remote only'
print(f'\nFinal: {row[0]}. {row[1]} {status}')

conn.close()