"""add business context fields to business profiles

Revision ID: fa96f1007c65
Revises: fc54f9e0c306
Create Date: 2026-07-08 15:08:16.637219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa96f1007c65'
down_revision: Union[str, Sequence[str], None] = 'fc54f9e0c306'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("business_profiles", sa.Column("business_type", sa.String(length=50), nullable=True))
    op.add_column("business_profiles", sa.Column("business_description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("business_profiles", "business_description")
    op.drop_column("business_profiles", "business_type")
