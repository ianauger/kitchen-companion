"""Migration script to add image_url and image_path columns to recipes table."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'kitchen_companion.db')

def migrate():
    """Add missing columns to recipes table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(recipes)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add image_url column if missing
    if 'image_url' not in columns:
        print("Adding image_url column...")
        cursor.execute("ALTER TABLE recipes ADD COLUMN image_url VARCHAR(1000)")
    
    # Add image_path column if missing
    if 'image_path' not in columns:
        print("Adding image_path column...")
        cursor.execute("ALTER TABLE recipes ADD COLUMN image_path VARCHAR(500)")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == '__main__':
    migrate()