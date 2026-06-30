"""add chilling equipment change records

Revision ID: aa7d7d38c9d5
Revises: 188a9090d675
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "aa7d7d38c9d5"
down_revision: Union[str, Sequence[str], None] = "188a9090d675"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_chilling_equipment_change_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_profile_id", sa.Integer(), nullable=False),
        sa.Column("chilling_equipment_id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_profile_id"],
            ["business_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["chilling_equipment_id"],
            ["business_chilling_equipment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_business_chilling_equipment_change_records_id"),
        "business_chilling_equipment_change_records",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_bce_change_records_business_profile_id",
        "business_chilling_equipment_change_records",
        ["business_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_bce_change_records_chilling_equipment_id",
        "business_chilling_equipment_change_records",
        ["chilling_equipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_bce_change_records_changed_by_user_id",
        "business_chilling_equipment_change_records",
        ["changed_by_user_id"],
        unique=False,
    )

    connection = op.get_bind()

    connection.execute(
        text(
            """
            INSERT INTO business_chilling_equipment_change_records (
                business_profile_id,
                chilling_equipment_id,
                change_type,
                field_name,
                old_value,
                new_value,
                changed_by_user_id,
                changed_at
            )
            SELECT
                business_profile_id,
                id,
                'baseline',
                'current_state',
                NULL,
                CONCAT(
                    'Change tracking started. Current state: ',
                    'asset_code=', equipment_asset_code,
                    '; name=', equipment_name,
                    '; use=', equipment_use,
                    '; type=', equipment_type,
                    '; temperature_check_method=', temperature_check_method,
                    '; is_active=', IF(is_active, 'true', 'false')
                ),
                NULL,
                CURRENT_TIMESTAMP
            FROM business_chilling_equipment
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bce_change_records_changed_by_user_id",
        table_name="business_chilling_equipment_change_records",
    )
    op.drop_index(
        "ix_bce_change_records_chilling_equipment_id",
        table_name="business_chilling_equipment_change_records",
    )
    op.drop_index(
        "ix_bce_change_records_business_profile_id",
        table_name="business_chilling_equipment_change_records",
    )
    op.drop_index(
        op.f("ix_business_chilling_equipment_change_records_id"),
        table_name="business_chilling_equipment_change_records",
    )
    op.drop_table("business_chilling_equipment_change_records")
