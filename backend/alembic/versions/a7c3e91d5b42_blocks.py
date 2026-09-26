"""add blocks table

Revision ID: a7c3e91d5b42
Revises: 90f21bbbca27
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e91d5b42"
down_revision: Union[str, None] = "90f21bbbca27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blocks",
        sa.Column("blocker_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blocked_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("blocker_id != blocked_id", name="block_no_self_block"),
    )
    op.create_index("ix_block_blocked", "blocks", ["blocked_id"])


def downgrade() -> None:
    op.drop_index("ix_block_blocked", table_name="blocks")
    op.drop_table("blocks")
