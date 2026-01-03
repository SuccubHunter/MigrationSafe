"""add generic_audit_records table

Revision ID: 0004_add_generic_records
Revises: None
Create Date: 2025-10-28 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from app.core.config import settings
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_add_generic_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generic_records",
        sa.Column("field_01", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("field_02", sa.String(length=255), nullable=True),
        sa.Column("field_03", sa.String(length=255), nullable=True, server_default="0"),
        sa.Column("field_04", sa.String(length=255), nullable=True, server_default="unknown"),
        sa.Column("field_05", sa.String(length=255), nullable=True),
        sa.Column("field_06", sa.String(length=255), nullable=True),
        sa.Column("field_07", sa.Date(), nullable=True),
        sa.Column("field_08", sa.Float(), nullable=True),
        sa.Column("field_09", sa.SmallInteger(), nullable=True),
        sa.Column("field_10", sa.SmallInteger(), nullable=True),
        sa.Column("field_11", sa.String(length=255), nullable=True),
        sa.Column("field_12", sa.String(length=255), nullable=True),
        sa.Column("field_13", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        sa.Column("field_14", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        sa.Column("field_15", sa.BigInteger(), nullable=True),
        sa.Column("field_16", sa.Integer(), nullable=True),
        sa.Column("field_17", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("field_18", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("field_19", sa.String(length=50), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("field_20", sa.String(length=1000), nullable=True),
        sa.Column("field_21", sa.String(length=100), nullable=False, server_default=sa.text("'Under review'")),
        sa.Column("field_22", sa.String(length=1000), nullable=True),
        schema=settings.DATABASE_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table(
        "generic_records",
        schema=settings.DATABASE_SCHEMA,
    )
