"""add generic boolean flag to abstract_mapping

Revision ID: 0006_add_generic_flag
Revises: 0005_add_generic_flags
Create Date: 2025-10-31 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from app.core.config import settings

# revision identifiers, used by Alembic.
revision = "0006_add_generic_flag"
down_revision = "0005_add_generic_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "abstract_mapping",
        sa.Column(
            "field_25",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=settings.DATABASE_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(
        "abstract_mapping",
        "field_25",
        schema=settings.DATABASE_SCHEMA,
    )
