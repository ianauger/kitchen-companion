"""Add prep session models — PrepSession, PrepSessionRecipe, PrepTask

Revision: add_prep_session_models
Create Date: 2026-05-15 21:53:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_prep_session_models'
down_revision = 'cca4cdb1b240'
branch_labels = None
depends_on = None


def upgrade():
    # ── prep_sessions ──────────────────────────────────────────────────
    op.create_table(
        'prep_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── prep_session_recipes (association with ordering) ────────────────
    op.create_table(
        'prep_session_recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('servings_multiplier', sa.Float(), nullable=True,
                  server_default='1.0'),
        sa.ForeignKeyConstraint(['session_id'], ['prep_sessions.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'recipe_id',
                            name='uix_session_recipe'),
    )

    # ── prep_tasks ─────────────────────────────────────────────────────
    op.create_table(
        'prep_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False,
                  server_default='mise'),
        sa.Column('recipe_id', sa.Integer(), nullable=True),
        sa.Column('estimated_minutes', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True,
                  server_default='0'),
        sa.Column('is_parallel', sa.Boolean(), nullable=True,
                  server_default='0'),
        sa.Column('completed', sa.Boolean(), nullable=True,
                  server_default='0'),
        sa.Column('depends_on', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['prep_sessions.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['depends_on'], ['prep_tasks.id'],
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Index on session_id for quick task queries
    op.create_index('ix_prep_tasks_session_id', 'prep_tasks', ['session_id'])
    op.create_index('ix_prep_tasks_sort_order', 'prep_tasks',
                    ['session_id', 'sort_order'])


def downgrade():
    op.drop_index('ix_prep_tasks_sort_order', table_name='prep_tasks')
    op.drop_index('ix_prep_tasks_session_id', table_name='prep_tasks')
    op.drop_table('prep_tasks')
    op.drop_table('prep_session_recipes')
    op.drop_table('prep_sessions')
