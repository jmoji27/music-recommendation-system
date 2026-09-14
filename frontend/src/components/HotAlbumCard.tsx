import { Link } from "react-router-dom";
import type { HotAlbum } from "../types";

export function HotAlbumCard({ album }: { album: HotAlbum }) {
  return (
    <Link to={`/albums/${album.spotify_id}`} className="card">
      {album.image_url ? <img src={album.image_url} alt={album.name} /> : <div className="card-image-placeholder" />}
      <div className="card-title">{album.name}</div>
      <div className="card-subtitle">{album.artist.name}</div>
      <div className="hot-badge">
        {album.review_count} review{album.review_count === 1 ? "" : "s"}
      </div>
    </Link>
  );
}
