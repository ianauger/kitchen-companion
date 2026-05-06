"""add shopping_items and notes tables

Revision ID: a1b2c3d4e5f6
Revises: 52bd626b279e
Create Date: 2026-05-06 05:37:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '52bd626b279e'
branch_labels = None
depends_on = None


def upgrade():
    # Create shopping_items table (if not exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER NOT NULL,
            name VARCHAR(500) NOT NULL,
            recipe_id INTEGER,
            purchased BOOLEAN DEFAULT 0 NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(recipe_id) REFERENCES recipes (id)
        )
    """)
    # Create index if not exists (SQLite will ignore duplicates)
    op.execute('CREATE INDEX IF NOT EXISTS ix_shopping_items_purchased ON shopping_items (purchased)')

    # Create notes table (if not exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(recipe_id) REFERENCES recipes (id)
        )
    """)


def downgrade():
    op.drop_table('notes')
    op.drop_index(op.f('ix_shopping_items_purchased'), table_name='shopping_items')
    op.drop_table('shopping_items')
