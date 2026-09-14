"""add google login: nullable spotify_id, google_id, identity check

Revision ID: de5327de3477
Revises: 074020a789af
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "de5327de3477"
down_revision: Union[str, None] = "074020a789af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "spotify_id", existing_type=sa.String(64), nullable=True)
    op.add_column("users", sa.Column("google_id", sa.String(64), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    op.create_check_constraint("user_has_an_identity", "users", "num_nonnulls(spotify_id, google_id) >= 1")


def downgrade() -> None:
    op.drop_constraint("user_has_an_identity", "users", type_="check")
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")
    op.alter_column("users", "spotify_id", existing_type=sa.String(64), nullable=False)
