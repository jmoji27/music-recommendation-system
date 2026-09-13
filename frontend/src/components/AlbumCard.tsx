import { Link } from "react-router-dom";
import type { AlbumSummary } from "../types";

export function AlbumCard({ album }: { album: AlbumSummary }) {
  return (
    <Link to={`/albums/${album.spotify_id}`} className="card">
      {album.image_url ? <img src={album.image_url} alt={album.name} /> : <div className="card-image-placeholder" />}
      <div className="card-title">{album.name}</div>
      <div className="card-subtitle">{album.artist.name}</div>
    </Link>
  );
}
