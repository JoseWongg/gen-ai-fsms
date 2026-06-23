"""add chilling equipment asset codes

Revision ID: 188a9090d675
Revises: 7e2c7a91f8b4
Create Date: 2026-06-23 17:14:38.266017
"""

from datetime import date
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "188a9090d675"
down_revision: Union[str, Sequence[str], None] = "7e2c7a91f8b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _asset_date_value(created_at):
    if created_at is None:
        return date.today().strftime("%Y%m%d")

    if hasattr(created_at, "strftime"):
        return created_at.strftime("%Y%m%d")

    created_text = str(created_at)

    if len(created_text) >= 10:
        return created_text[:10].replace("-", "")

    return date.today().strftime("%Y%m%d")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "business_chilling_equipment",
        sa.Column("equipment_asset_code", sa.String(length=50), nullable=True),
    )

    op.add_column(
        "daily_shift_chilling_temperature_checks",
        sa.Column("equipment_asset_code_snapshot", sa.String(length=50), nullable=True),
    )

    connection = op.get_bind()

    equipment_rows = connection.execute(
        text("SELECT id, created_at FROM business_chilling_equipment ORDER BY id ASC")
    ).fetchall()

    for row in equipment_rows:
        equipment_id = row[0]
        created_at = row[1]
        asset_date = _asset_date_value(created_at)
        asset_code = f"CHILL-{asset_date}-{equipment_id:04d}"

        connection.execute(
            text(
                "UPDATE business_chilling_equipment "
                "SET equipment_asset_code = :asset_code "
                "WHERE id = :equipment_id"
            ),
            {
                "asset_code": asset_code,
                "equipment_id": equipment_id,
            },
        )

    check_rows = connection.execute(
        text(
            "SELECT c.id, e.equipment_asset_code "
            "FROM daily_shift_chilling_temperature_checks c "
            "JOIN business_chilling_equipment e "
            "ON c.chilling_equipment_id = e.id "
            "ORDER BY c.id ASC"
        )
    ).fetchall()

    for row in check_rows:
        check_id = row[0]
        asset_code = row[1]

        connection.execute(
            text(
                "UPDATE daily_shift_chilling_temperature_checks "
                "SET equipment_asset_code_snapshot = :asset_code "
                "WHERE id = :check_id"
            ),
            {
                "asset_code": asset_code,
                "check_id": check_id,
            },
        )

    op.alter_column(
        "business_chilling_equipment",
        "equipment_asset_code",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.alter_column(
        "daily_shift_chilling_temperature_checks",
        "equipment_asset_code_snapshot",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_business_chilling_equipment_asset_code",
        "business_chilling_equipment",
        ["equipment_asset_code"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_business_chilling_equipment_asset_code",
        "business_chilling_equipment",
        type_="unique",
    )

    op.drop_column(
        "daily_shift_chilling_temperature_checks",
        "equipment_asset_code_snapshot",
    )

    op.drop_column(
        "business_chilling_equipment",
        "equipment_asset_code",
    )
