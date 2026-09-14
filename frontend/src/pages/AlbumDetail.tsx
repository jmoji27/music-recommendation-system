import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../api/client";
import type { AlbumDetail as AlbumDetailType, ReviewItem } from "../types";

export function AlbumDetail() {
  const { spotifyId } = useParams<{ spotifyId: string }>();
  const { user } = useAuth();
  const [album, setAlbum] = useState<AlbumDetailType | null>(null);
  const [reviews, setReviews] = useState<ReviewItem[] | null>(null);

  async function loadReviews() {
    if (!spotifyId) return;
    setReviews(await api.get<ReviewItem[]>(`/albums/${spotifyId}/reviews`));
  }

  useEffect(() => {
    if (!spotifyId) return;
    api.get<AlbumDetailType>(`/catalog/albums/${spotifyId}`).then(setAlbum);
    loadReviews();
  }, [spotifyId]);

  if (!album) return <p className="muted">Loading…</p>;

  return (
    <div className="album-detail">
      <div className="album-header">
        {album.image_url && <img src={album.image_url} alt={album.name} />}
        <div>
          <h1>{album.name}</h1>
          <p className="muted">
            {album.artist.name} · {album.release_date}
          </p>
        </div>
      </div>

      <section>
        <h2>Tracklist</h2>
        <ol className="tracklist">
          {album.tracks.map((track) => (
            <li key={track.id}>{track.name}</li>
          ))}
        </ol>
      </section>

      <section>
        <h2>Reviews</h2>
        {user ? (
          <ReviewForm spotifyId={spotifyId!} onSubmitted={loadReviews} />
        ) : (
          <p className="muted">
            <Link to="/">Log in</Link> to leave a review.
          </p>
        )}

        {reviews === null ? (
          <p className="muted">Loading…</p>
        ) : reviews.length === 0 ? (
          <p className="muted">No reviews yet — be the first.</p>
        ) : (
          reviews.map((review) => <Review key={review.id} review={review} onChanged={loadReviews} />)
        )}
      </section>
    </div>
  );
}

function ReviewForm({ spotifyId, onSubmitted }: { spotifyId: string; onSubmitted: () => void }) {
  const [stars, setStars] = useState(5);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/albums/${spotifyId}/reviews`, { stars, content: content.trim() || null });
      setContent("");
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      <select value={stars} onChange={(event) => setStars(Number(event.target.value))}>
        {[5, 4, 3, 2, 1].map((n) => (
          <option key={n} value={n}>
            {"★".repeat(n)}
          </option>
        ))}
      </select>
      <textarea
        placeholder="What did you think? (optional)"
        value={content}
        onChange={(event) => setContent(event.target.value)}
      />
      <button type="submit">Post review</button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function Review({ review, onChanged }: { review: ReviewItem; onChanged: () => void }) {
  const { user } = useAuth();
  const [commentText, setCommentText] = useState("");

  async function like() {
    try {
      await api.post(`/reviews/${review.id}/like`);
      onChanged();
    } catch {
      // Already liked — nothing to do, the count just won't move.
    }
  }

  async function submitComment(event: React.FormEvent) {
    event.preventDefault();
    if (!commentText.trim()) return;
    await api.post(`/reviews/${review.id}/comments`, { content: commentText.trim() });
    setCommentText("");
    onChanged();
  }

  async function likeComment(commentId: number) {
    try {
      await api.post(`/comments/${commentId}/like`);
      onChanged();
    } catch {
      // Already liked.
    }
  }

  return (
    <div className="review">
      <div className="review-header">
        <strong>{review.user.display_name}</strong>
        {review.stars && <span>{"★".repeat(review.stars)}</span>}
      </div>
      {review.content && <p>{review.content}</p>}
      <button onClick={like} disabled={!user}>
        ♥ {review.like_count}
      </button>

      <div className="comments">
        {review.comments.map((comment) => (
          <div key={comment.id} className="comment">
            <strong>{comment.user.display_name}</strong>: {comment.content}{" "}
            <button onClick={() => likeComment(comment.id)} disabled={!user}>
              ♥ {comment.like_count}
            </button>
          </div>
        ))}
        {user && (
          <form onSubmit={submitComment} className="comment-form">
            <input
              type="text"
              placeholder="Add a comment…"
              value={commentText}
              onChange={(event) => setCommentText(event.target.value)}
            />
            <button type="submit">Reply</button>
          </form>
        )}
      </div>
    </div>
  );
}
