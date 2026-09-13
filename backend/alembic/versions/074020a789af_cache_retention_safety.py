"""cache retention safety: cached_at timestamps + restrict deletes

Adds cached_at to artists/albums/tracks (needed by the monthly
cache-retention job to measure "unused for 6 months"), and tightens
interactions.artist_id/album_id/track_id from ON DELETE CASCADE to
RESTRICT: that job deletes catalog rows with zero interactions, and
RESTRICT makes Postgres refuse the delete loudly if that check is ever
wrong, instead of silently cascading away a real review/comment/like.

Revision ID: 074020a789af
Revises: c0b6e28d1d3b
Create Date: 2026-09-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "074020a789af"
down_revision: Union[str, None] = "c0b6e28d1d3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("artists", "albums", "tracks"):
        op.add_column(
            table,
            sa.Column("cached_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    op.drop_constraint("interactions_artist_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_artist_id_fkey", "interactions", "artists", ["artist_id"], ["id"], ondelete="RESTRICT"
    )

    op.drop_constraint("interactions_album_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_album_id_fkey", "interactions", "albums", ["album_id"], ["id"], ondelete="RESTRICT"
    )

    op.drop_constraint("interactions_track_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_track_id_fkey", "interactions", "tracks", ["track_id"], ["id"], ondelete="RESTRICT"
    )


def downgrade() -> None:
    op.drop_constraint("interactions_track_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_track_id_fkey", "interactions", "tracks", ["track_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("interactions_album_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_album_id_fkey", "interactions", "albums", ["album_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("interactions_artist_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_artist_id_fkey", "interactions", "artists", ["artist_id"], ["id"], ondelete="CASCADE"
    )

    for table in ("artists", "albums", "tracks"):
        op.drop_column(table, "cached_at")
