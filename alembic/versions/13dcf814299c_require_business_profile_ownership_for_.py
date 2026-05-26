"""require business profile ownership for users

Revision ID: 13dcf814299c
Revises: d6a4036401fd
Create Date: 2026-05-26 18:17:22.772560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '13dcf814299c'
down_revision: Union[str, Sequence[str], None] = 'd6a4036401fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "fk_users_business_profile_id_business_profiles",
        "users",
        type_="foreignkey",
    )

    op.alter_column(
        "users",
        "business_profile_id",
        existing_type=mysql.INTEGER(),
        nullable=False,
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

    op.alter_column(
        "users",
        "business_profile_id",
        existing_type=mysql.INTEGER(),
        nullable=True,
    )

    op.create_foreign_key(
        "fk_users_business_profile_id_business_profiles",
        "users",
        "business_profiles",
        ["business_profile_id"],
        ["id"],
    )
