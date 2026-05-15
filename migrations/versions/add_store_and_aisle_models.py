"""add stores, store_aisles, aisle_overrides, and meal_plans tables

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # ── stores table ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            created_at DATETIME,
            PRIMARY KEY (id)
        )
    """)

    # ── store_aisles table ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS store_aisles (
            id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            name VARCHAR(100) NOT NULL,
            sort_order INTEGER DEFAULT 0,
            PRIMARY KEY (id),
            FOREIGN KEY(store_id) REFERENCES stores (id),
            UNIQUE(store_id, name)
        )
    """)

    # ── aisle_overrides table ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS aisle_overrides (
            id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            item_name_normalized VARCHAR(200) NOT NULL,
            aisle_id INTEGER NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(store_id) REFERENCES stores (id),
            FOREIGN KEY(aisle_id) REFERENCES store_aisles (id),
            UNIQUE(store_id, item_name_normalized)
        )
    """)

    # ── meal_plans table ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS meal_plans (
            id INTEGER NOT NULL,
            date DATE NOT NULL,
            meal_type VARCHAR(20) NOT NULL,
            recipe_id INTEGER,
            notes TEXT,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(recipe_id) REFERENCES recipes (id),
            UNIQUE(date, meal_type)
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS ix_meal_plans_date ON meal_plans (date)')

    # ── Add aisle_override_id to shopping_items ───────────────────────
    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we do the
    # table-rebuild dance only if the column doesn't exist yet.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('shopping_items')]

    if 'aisle_override_id' not in existing_cols:
        # Rebuild shopping_items with the new column
        op.execute("""
            CREATE TABLE shopping_items_new (
                id INTEGER NOT NULL,
                name VARCHAR(500) NOT NULL,
                recipe_id INTEGER,
                purchased BOOLEAN DEFAULT 0 NOT NULL,
                aisle_override_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY(recipe_id) REFERENCES recipes (id),
                FOREIGN KEY(aisle_override_id) REFERENCES aisle_overrides (id)
            )
        """)
        op.execute("""
            INSERT INTO shopping_items_new (id, name, recipe_id, purchased, created_at, updated_at)
            SELECT id, name, recipe_id, purchased, created_at, updated_at FROM shopping_items
        """)
        op.execute('DROP TABLE shopping_items')
        op.execute('ALTER TABLE shopping_items_new RENAME TO shopping_items')
        op.execute('CREATE INDEX IF NOT EXISTS ix_shopping_items_purchased ON shopping_items (purchased)')


def downgrade():
    # Remove aisle_override_id from shopping_items
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('shopping_items')]

    if 'aisle_override_id' in existing_cols:
        op.execute("""
            CREATE TABLE shopping_items_old (
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
        op.execute("""
            INSERT INTO shopping_items_old (id, name, recipe_id, purchased, created_at, updated_at)
            SELECT id, name, recipe_id, purchased, created_at, updated_at FROM shopping_items
        """)
        op.execute('DROP TABLE shopping_items')
        op.execute('ALTER TABLE shopping_items_old RENAME TO shopping_items')
        op.execute('CREATE INDEX IF NOT EXISTS ix_shopping_items_purchased ON shopping_items (purchased)')

    op.execute('DROP TABLE IF EXISTS meal_plans')
    op.execute('DROP TABLE IF EXISTS aisle_overrides')
    op.execute('DROP TABLE IF EXISTS store_aisles')
    op.execute('DROP TABLE IF EXISTS stores')
