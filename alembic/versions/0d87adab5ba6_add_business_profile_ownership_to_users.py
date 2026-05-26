"""add business profile ownership to users

Revision ID: 0d87adab5ba6
Revises: 8136aaf8b524
Create Date: 2026-05-26 11:19:44.550663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d87adab5ba6'
down_revision: Union[str, Sequence[str], None] = '8136aaf8b524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("business_profile_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_users_business_profile_id"),
        "users",
        ["business_profile_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_business_profile_id_business_profiles",
        "users",
        "business_profiles",
        ["business_profile_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_users_business_profile_id_business_profiles",
        "users",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_users_business_profile_id"), table_name="users")
    op.drop_column("users", "business_profile_id")
