import sqlite3
import os

# Connect to the database
db_path = '/Users/iauger/.openclaw/workspace/projects/kitchen-companion-app/kitchen_companion.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Update recipe 1 with a new image URL
cursor.execute("""
    UPDATE recipe 
    SET image_url = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=80',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = 1
""")

# Update recipe 9 with a new image URL
cursor.execute("""
    UPDATE recipe 
    SET image_url = 'https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=800&q=80',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = 9
""")

conn.commit()

# Verify updates
cursor.execute("SELECT id, title, image_url, image_path FROM recipe WHERE id IN (1, 9)")
print("Updated recipes:")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Title: {row[1]}, image_url: {row[2][:50]}..., image_path: {row[3]}")

conn.close()
print("\nDone!")
