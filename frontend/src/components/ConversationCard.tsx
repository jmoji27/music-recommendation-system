import { Link } from "react-router-dom";
import type { AlbumConversation } from "../types";

export function ConversationCard({ conversation }: { conversation: AlbumConversation }) {
  const { album, reviews } = conversation;
  const totalComments = reviews.reduce((sum, review) => sum + review.comments.length, 0);
  const latest = reviews[0];

  return (
    <Link to={`/albums/${album.spotify_id}`} className="conversation-card">
      {album.image_url ? <img src={album.image_url} alt={album.name} /> : <div className="card-image-placeholder" />}
      <div className="conversation-body">
        <div className="card-title">{album.name}</div>
        <div className="card-subtitle">{album.artist.name}</div>
        <p className="conversation-preview">
          <strong>{latest.user.display_name}</strong>
          {latest.stars && <span> {"★".repeat(latest.stars)}</span>}
          {latest.content && <>: {latest.content}</>}
        </p>
        <div className="muted conversation-meta">
          {reviews.length} review{reviews.length === 1 ? "" : "s"}
          {totalComments > 0 && ` · ${totalComments} comment${totalComments === 1 ? "" : "s"}`}
        </div>
      </div>
    </Link>
  );
}
