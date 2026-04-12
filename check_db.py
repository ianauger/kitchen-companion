from sqlalchemy import text
from app import create_app, db

app = create_app('development')
with app.app_context():
    count = db.session.execute(text("SELECT count(*) FROM recipe")).scalar()
    print(f"Recipe count: {count}")
