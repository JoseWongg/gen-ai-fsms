"""Add FSMS responsible person fields

Revision ID: a6c1d9e4f2b7
Revises: fc96fd58736d
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "a6c1d9e4f2b7"
down_revision = "fc96fd58736d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "business_profiles",
        sa.Column(
            "fsms_responsible_person_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "business_profiles",
        sa.Column(
            "fsms_responsible_person_name",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.create_index(
        op.f(
            "ix_business_profiles_"
            "fsms_responsible_person_user_id"
        ),
        "business_profiles",
        ["fsms_responsible_person_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        (
            "fk_business_profiles_"
            "fsms_responsible_person_user_id_users"
        ),
        "business_profiles",
        "users",
        ["fsms_responsible_person_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        (
            "fk_business_profiles_"
            "fsms_responsible_person_user_id_users"
        ),
        "business_profiles",
        type_="foreignkey",
    )
    op.drop_index(
        op.f(
            "ix_business_profiles_"
            "fsms_responsible_person_user_id"
        ),
        table_name="business_profiles",
    )
    op.drop_column(
        "business_profiles",
        "fsms_responsible_person_name",
    )
    op.drop_column(
        "business_profiles",
        "fsms_responsible_person_user_id",
    )
