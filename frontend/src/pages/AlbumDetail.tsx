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
        {user && reviews?.some((r) => r.user.id === user.id) ? null : user ? (
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
  const [editing, setEditing] = useState(false);
  const [editStars, setEditStars] = useState<number | null>(review.stars);
  const [editContent, setEditContent] = useState(review.content ?? "");
  const [error, setError] = useState<string | null>(null);
  const isMine = user?.id === review.user.id;

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  const toggleLike = (path: string, liked: boolean) =>
    run(() => (liked ? api.delete(path) : api.post(path)));

  async function saveEdit(event: React.FormEvent) {
    event.preventDefault();
    await run(async () => {
      await api.put(`/reviews/${review.id}`, { stars: editStars, content: editContent.trim() || null });
      setEditing(false);
    });
  }

  async function remove() {
    if (!window.confirm("Delete this review? Its comments and likes will be deleted too.")) return;
    await run(() => api.delete(`/reviews/${review.id}`));
  }

  async function submitComment(event: React.FormEvent) {
    event.preventDefault();
    if (!commentText.trim()) return;
    await run(async () => {
      await api.post(`/reviews/${review.id}/comments`, { content: commentText.trim() });
      setCommentText("");
    });
  }

  return (
    <div className="review">
      <div className="review-header">
        <strong>{review.user.display_name}</strong>
        {review.stars && <span>{"★".repeat(review.stars)}</span>}
        {review.edited && <span className="muted edited-tag">(edited)</span>}
      </div>

      {editing ? (
        <form className="review-form" onSubmit={saveEdit}>
          <select
            aria-label="Stars"
            value={editStars ?? ""}
            onChange={(event) => setEditStars(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">No rating</option>
            {[5, 4, 3, 2, 1].map((n) => (
              <option key={n} value={n}>
                {"★".repeat(n)}
              </option>
            ))}
          </select>
          <textarea aria-label="Review text" value={editContent} onChange={(event) => setEditContent(event.target.value)} />
          <button type="submit">Save</button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      ) : (
        review.content && <p>{review.content}</p>
      )}

      <button
        onClick={() => toggleLike(`/reviews/${review.id}/like`, review.liked_by_me)}
        disabled={!user}
        aria-pressed={review.liked_by_me}
        title={review.liked_by_me ? "Unlike" : "Like"}
      >
        {review.liked_by_me ? "♥" : "♡"} {review.like_count}
      </button>
      {isMine && !editing && (
        <>
          <button onClick={() => setEditing(true)}>Edit</button>
          <button onClick={remove}>Delete</button>
        </>
      )}
      {error && <p className="error">{error}</p>}

      <div className="comments">
        {review.comments.map((comment) => (
          <CommentRow
            key={comment.id}
            comment={comment}
            canModerate={isMine}
            run={run}
            toggleLike={toggleLike}
          />
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

function CommentRow({
  comment,
  canModerate,
  run,
  toggleLike,
}: {
  comment: ReviewItem["comments"][number];
  canModerate: boolean;
  run: (action: () => Promise<unknown>) => Promise<void>;
  toggleLike: (path: string, liked: boolean) => Promise<void>;
}) {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(comment.content);
  const isMine = user?.id === comment.user.id;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    await run(async () => {
      await api.put(`/comments/${comment.id}`, { content: text.trim() });
      setEditing(false);
    });
  }

  return (
    <div className="comment">
      <strong>{comment.user.display_name}</strong>:{" "}
      {editing ? (
        <form className="comment-form" onSubmit={save}>
          <input type="text" aria-label="Comment text" value={text} onChange={(event) => setText(event.target.value)} />
          <button type="submit">Save</button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          {comment.content}
          {comment.edited && <span className="muted edited-tag"> (edited)</span>}{" "}
        </>
      )}
      <button
        onClick={() => toggleLike(`/comments/${comment.id}/like`, comment.liked_by_me)}
        disabled={!user}
        aria-pressed={comment.liked_by_me}
        title={comment.liked_by_me ? "Unlike" : "Like"}
      >
        {comment.liked_by_me ? "♥" : "♡"} {comment.like_count}
      </button>
      {isMine && !editing && <button onClick={() => setEditing(true)}>Edit</button>}
      {(isMine || canModerate) && !editing && (
        <button onClick={() => run(() => api.delete(`/comments/${comment.id}`))}>Delete</button>
      )}
    </div>
  );
}
