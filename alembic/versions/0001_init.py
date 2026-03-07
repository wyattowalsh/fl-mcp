"""init tables

Revision ID: 0001
Revises: 
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactionrecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpointrecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checkpoint_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("checkpointrecord")
    op.drop_table("transactionrecord")
