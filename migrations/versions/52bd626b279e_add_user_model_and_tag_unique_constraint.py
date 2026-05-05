"""add user model and tag unique constraint

Revision ID: 52bd626b279e
Revises: cca4cdb1b240
Create Date: 2026-05-05 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '52bd626b279e'
down_revision = 'cca4cdb1b240'
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Add unique constraint on tags (name, tag_type) to prevent duplicates
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.create_unique_constraint('uix_tag_name_type', ['name', 'tag_type'])


def downgrade():
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.drop_constraint('uix_tag_name_type', type_='unique')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_table('users')
