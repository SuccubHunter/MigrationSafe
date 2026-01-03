"""Test migration

Revision ID: 001testmigration
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "001testmigration"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create test table
    op.create_table(
        "test_table",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("test_table")
