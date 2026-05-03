#!/usr/bin/env python3
"""Fix recipe 12 image using Unsplash source URLs."""
import os
import sqlite3
import requests
import uuid

DB_PATH = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/kitchen_companion.db'
UPLOAD_DIR = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/app/static/uploads/recipes'

def download_image(url, recipe_id):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        resp = requests.get(url, timeout=15, stream=True, allow_redirects=True, headers=headers)
        resp.raise_for_status()
        # Determine extension
        content_type = resp.headers.get('Content-Type', '')
        if 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.jpg'
        filename = f'recipe_{recipe_id}_{uuid.uuid4().hex[:8]}{ext}'
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        relative_path = f'uploads/recipes/{filename}'
        print(f'  Downloaded: {filepath} ({os.path.getsize(filepath)} bytes, type={content_type})')
        return relative_path
    except Exception as e:
        print(f'  Download failed for {url[:60]}...: {e}')
        return None

# Try multiple approaches for Japanese curry image
urls = [
    'https://images.unsplash.com/photo-1569718212165-3a8278d61f43?w=800&q=80',
    'https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=800&q=80',  # Indian food (already works for recipe 6)
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

for url in urls:
    print(f'Trying: {url[:70]}...')
    relative_path = download_image(url, 12)
    if relative_path:
        cursor.execute('UPDATE recipes SET image_url = ?, image_path = ? WHERE id = 12', (url, relative_path))
        conn.commit()
        print(f'  SUCCESS: image_path = {relative_path}')
        break
    else:
        print('  Failed, trying next...')

# Final check
cursor.execute('SELECT id, title, image_path FROM recipes WHERE id = 12')
row = cursor.fetchone()
status = '✅' if row[2] else '❌ remote only'
print(f'\nFinal: {row[0]}. {row[1]} {status}')

conn.close()