"""Widen onboarding session state JSON

Revision ID: f4a8c2d1e9b6
Revises: d3cbecd48c9c
Create Date: 2026-07-13
"""

from alembic import op
from sqlalchemy.dialects import mysql


revision = "f4a8c2d1e9b6"
down_revision = "d3cbecd48c9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "onboarding_sessions",
        "state_json",
        existing_type=mysql.TEXT(),
        type_=mysql.LONGTEXT(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "onboarding_sessions",
        "state_json",
        existing_type=mysql.LONGTEXT(),
        type_=mysql.TEXT(),
        existing_nullable=True,
    )
