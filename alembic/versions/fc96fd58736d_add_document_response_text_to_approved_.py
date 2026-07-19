"""Add document response text to approved safety point responses

Revision ID: fc96fd58736d
Revises: f4a8c2d1e9b6
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "fc96fd58736d"
down_revision = "f4a8c2d1e9b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approved_safety_point_responses",
        sa.Column(
            "document_response_text",
            sa.Text(),
            nullable=True,
        ),
    )

    approved_safety_point_responses = sa.table(
        "approved_safety_point_responses",
        sa.column("response_text", sa.Text()),
        sa.column("document_response_text", sa.Text()),
    )

    op.execute(
        approved_safety_point_responses.update().values(
            document_response_text=(
                approved_safety_point_responses.c.response_text
            )
        )
    )

    op.alter_column(
        "approved_safety_point_responses",
        "document_response_text",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column(
        "approved_safety_point_responses",
        "document_response_text",
    )
