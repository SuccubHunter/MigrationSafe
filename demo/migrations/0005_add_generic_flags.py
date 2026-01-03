"""add generic status fields to abstract_records_completed

Revision ID: 0005_add_generic_flags
Revises: 0004_add_generic_records
Create Date: 2025-10-28 12:20:00.000000
"""

import sqlalchemy as sa
from alembic import op
from app.core.config import settings

# revision identifiers, used by Alembic.
revision = "0005_add_generic_flags"
down_revision = "0004_add_generic_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add generic status and flag fields
    op.add_column(
        "abstract_records_completed",
        sa.Column(
            "field_23",
            sa.String(length=50),
            nullable=True,
            server_default=sa.text("'done'"),
        ),
        schema=settings.DATABASE_SCHEMA,
    )
    op.add_column(
        "abstract_records_completed",
        sa.Column(
            "field_24",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
        schema=settings.DATABASE_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(
        "abstract_records_completed",
        "field_24",
        schema=settings.DATABASE_SCHEMA,
    )
    op.drop_column(
        "abstract_records_completed",
        "field_23",
        schema=settings.DATABASE_SCHEMA,
    )
