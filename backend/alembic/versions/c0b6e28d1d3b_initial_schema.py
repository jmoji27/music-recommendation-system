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

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artist_id", sa.Integer(), sa.ForeignKey("artists.id", ondelete="CASCADE"), nullable=True),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("stars", sa.SmallInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(artist_id, album_id, track_id) = 1", name="review_exactly_one_target"
        ),
        sa.CheckConstraint("stars IS NOT NULL OR body IS NOT NULL", name="review_has_stars_or_body"),
        sa.CheckConstraint("stars IS NULL OR stars BETWEEN 1 AND 5", name="review_stars_range"),
    )
    op.create_index(
        "uq_review_user_artist", "reviews", ["user_id", "artist_id"], unique=True,
        postgresql_where=sa.text("artist_id IS NOT NULL"),
    )
    op.create_index(
        "uq_review_user_album", "reviews", ["user_id", "album_id"], unique=True,
        postgresql_where=sa.text("album_id IS NOT NULL"),
    )
    op.create_index(
        "uq_review_user_track", "reviews", ["user_id", "track_id"], unique=True,
        postgresql_where=sa.text("track_id IS NOT NULL"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "comment_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("num_nonnulls(review_id, comment_id) = 1", name="like_exactly_one_target"),
    )
    op.create_index(
        "uq_like_user_review", "likes", ["user_id", "review_id"], unique=True,
        postgresql_where=sa.text("review_id IS NOT NULL"),
    )
    op.create_index(
        "uq_like_user_comment", "likes", ["user_id", "comment_id"], unique=True,
        postgresql_where=sa.text("comment_id IS NOT NULL"),
    )

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
    op.drop_table("likes")
    op.drop_table("comments")
    op.drop_table("reviews")
    op.drop_table("tracks")
    op.drop_table("albums")
    op.drop_table("artists")
    op.drop_table("users")
