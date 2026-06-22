"""add daily shift chilling temperature checks

Revision ID: 7e2c7a91f8b4
Revises: 4c79c78e07c2
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e2c7a91f8b4"
down_revision: Union[str, None] = "4c79c78e07c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_shift_chilling_temperature_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("daily_shift_id", sa.Integer(), nullable=False),
        sa.Column("chilling_equipment_id", sa.Integer(), nullable=False),
        sa.Column("equipment_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("equipment_use_snapshot", sa.String(length=50), nullable=False),
        sa.Column("equipment_type_snapshot", sa.String(length=50), nullable=False),
        sa.Column(
            "temperature_check_method_snapshot",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("am_temperature", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("am_recorded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("am_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pm_temperature", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("pm_recorded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("pm_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["am_recorded_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["chilling_equipment_id"],
            ["business_chilling_equipment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["daily_shift_id"],
            ["daily_shifts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["pm_recorded_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "daily_shift_id",
            "chilling_equipment_id",
            name="uq_daily_shift_chilling_temperature_equipment",
        ),
    )
    op.create_index(
        op.f("ix_daily_shift_chilling_temperature_checks_id"),
        "daily_shift_chilling_temperature_checks",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_shift_chilling_temperature_checks_daily_shift_id"),
        "daily_shift_chilling_temperature_checks",
        ["daily_shift_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_shift_chilling_temperature_checks_chilling_equipment_id"),
        "daily_shift_chilling_temperature_checks",
        ["chilling_equipment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_daily_shift_chilling_temperature_checks_chilling_equipment_id"),
        table_name="daily_shift_chilling_temperature_checks",
    )
    op.drop_index(
        op.f("ix_daily_shift_chilling_temperature_checks_daily_shift_id"),
        table_name="daily_shift_chilling_temperature_checks",
    )
    op.drop_index(
        op.f("ix_daily_shift_chilling_temperature_checks_id"),
        table_name="daily_shift_chilling_temperature_checks",
    )
    op.drop_table("daily_shift_chilling_temperature_checks")
