"""add business context facts

Revision ID: d3cbecd48c9c
Revises: fa96f1007c65
Create Date: 2026-07-08 18:36:14.027903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3cbecd48c9c'
down_revision: Union[str, Sequence[str], None] = 'fa96f1007c65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "business_context_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_profile_id", sa.Integer(), nullable=False),
        sa.Column("workflow_session_id", sa.Integer(), nullable=True),
        sa.Column("source_safety_point_id", sa.String(length=100), nullable=True),
        sa.Column("source_user_message", sa.Text(), nullable=True),
        sa.Column("fact_type", sa.String(length=100), nullable=False),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("normalised_fact", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="unverified_user_statement",
            nullable=False,
        ),
        sa.Column(
            "usage_scope",
            sa.String(length=50),
            server_default="personalisation_only",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["business_profile_id"],
            ["business_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_session_id"],
            ["onboarding_sessions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_business_context_facts_business_profile_id",
        "business_context_facts",
        ["business_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_workflow_session_id",
        "business_context_facts",
        ["workflow_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_source_safety_point_id",
        "business_context_facts",
        ["source_safety_point_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_fact_type",
        "business_context_facts",
        ["fact_type"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_status",
        "business_context_facts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_usage_scope",
        "business_context_facts",
        ["usage_scope"],
        unique=False,
    )
    op.create_index(
        "ix_business_context_facts_created_by_user_id",
        "business_context_facts",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_business_context_facts_created_by_user_id",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_usage_scope",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_status",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_fact_type",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_source_safety_point_id",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_workflow_session_id",
        table_name="business_context_facts",
    )
    op.drop_index(
        "ix_business_context_facts_business_profile_id",
        table_name="business_context_facts",
    )
    op.drop_table("business_context_facts")
