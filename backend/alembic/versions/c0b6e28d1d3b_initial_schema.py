"""initial schema

Revision ID: c0b6e28d1d3b
Revises:
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0b6e28d1d3b"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spotify_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("spotify_access_token_encrypted", sa.String(2048), nullable=True),
        sa.Column("spotify_refresh_token_encrypted", sa.String(2048), nullable=True),
        sa.Column("spotify_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_spotify_id", "users", ["spotify_id"], unique=True)

    op.create_table(
        "artists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spotify_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("genres", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=True),
    )
    op.create_index("ix_artists_spotify_id", "artists", ["spotify_id"], unique=True)

    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spotify_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "artist_id", sa.Integer(), sa.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("release_date", sa.String(10), nullable=True),
        sa.Column("image_url", sa.String(512), nullable=True),
    )
    op.create_index("ix_albums_spotify_id", "albums", ["spotify_id"], unique=True)

    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spotify_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "artist_id", sa.Integer(), sa.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tracks_spotify_id", "tracks", ["spotify_id"], unique=True)

    # A single table for ratings/reviews, comments, and likes, discriminated
    # by `type`. type='review' targets exactly one of artist/album/track
    # (exclusive arc). type IN ('comment','like') targets a parent
    # interaction instead (the review, or another comment for a like) —
    # Letterboxd-style: you comment on/like a specific review, not the
    # music entity directly.
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "type",
            sa.Enum("review", "comment", "like", name="interaction_type"),
            nullable=False,
        ),
        sa.Column("artist_id", sa.Integer(), sa.ForeignKey("artists.id", ondelete="CASCADE"), nullable=True),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "parent_interaction_id",
            sa.Integer(),
            sa.ForeignKey("interactions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("stars", sa.SmallInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "("
            "  type = 'review'"
            "  AND num_nonnulls(artist_id, album_id, track_id) = 1"
            "  AND parent_interaction_id IS NULL"
            ") OR ("
            "  type IN ('comment', 'like')"
            "  AND parent_interaction_id IS NOT NULL"
            "  AND artist_id IS NULL AND album_id IS NULL AND track_id IS NULL"
            ")",
            name="interaction_target_shape",
        ),
        sa.CheckConstraint(
            "type != 'review' OR stars IS NOT NULL OR content IS NOT NULL",
            name="interaction_review_has_stars_or_content",
        ),
        sa.CheckConstraint("stars IS NULL OR stars BETWEEN 1 AND 5", name="interaction_stars_range"),
        sa.CheckConstraint(
            "type != 'comment' OR content IS NOT NULL", name="interaction_comment_has_content"
        ),
        sa.CheckConstraint("type != 'like' OR content IS NULL", name="interaction_like_has_no_content"),
    )
    op.create_index(
        "uq_interaction_user_artist_review", "interactions", ["user_id", "artist_id"], unique=True,
        postgresql_where=sa.text("type = 'review' AND artist_id IS NOT NULL"),
    )
    op.create_index(
        "uq_interaction_user_album_review", "interactions", ["user_id", "album_id"], unique=True,
        postgresql_where=sa.text("type = 'review' AND album_id IS NOT NULL"),
    )
    op.create_index(
        "uq_interaction_user_track_review", "interactions", ["user_id", "track_id"], unique=True,
        postgresql_where=sa.text("type = 'review' AND track_id IS NOT NULL"),
    )
    op.create_index(
        "uq_interaction_user_like_parent", "interactions", ["user_id", "parent_interaction_id"], unique=True,
        postgresql_where=sa.text("type = 'like'"),
    )
    op.create_index("ix_interaction_parent", "interactions", ["parent_interaction_id"])

    op.create_table(
        "follows",
        sa.Column(
            "follower_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "followed_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("follower_id != followed_id", name="follow_no_self_follow"),
    )

    # Postgres ENUM types are created automatically as part of the
    # CREATE TABLE below (SQLAlchemy hooks this via the column's type),
    # so no separate create() call is needed here.
    time_range = sa.Enum("short_term", "medium_term", "long_term", name="time_range")

    op.create_table(
        "listening_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("time_range", time_range, nullable=False),
        sa.Column("top_artist_spotify_ids", sa.JSON(), nullable=False),
        sa.Column("top_track_spotify_ids", sa.JSON(), nullable=False),
        sa.Column("genre_counts", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("listening_snapshots")
    # Unlike create_table, drop_table-by-name has no column-type info, so
    # the enum type isn't dropped automatically the way it's auto-created
    # on upgrade — it needs an explicit drop here.
    sa.Enum(name="time_range").drop(op.get_bind(), checkfirst=True)
    op.drop_table("follows")
    op.drop_table("interactions")
    sa.Enum(name="interaction_type").drop(op.get_bind(), checkfirst=True)
    op.drop_table("tracks")
    op.drop_table("albums")
    op.drop_table("artists")
    op.drop_table("users")
