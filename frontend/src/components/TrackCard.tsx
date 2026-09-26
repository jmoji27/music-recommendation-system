import { Link } from "react-router-dom";
import type { TopTrackCard } from "../types";

/** Tracks have no page of their own; the card opens the album they're on. */
export function TrackCard({ track }: { track: TopTrackCard }) {
  return (
    <Link to={`/albums/${track.album.spotify_id}`} className="card">
      {track.album.image_url ? (
        <img src={track.album.image_url} alt={track.album.name} />
      ) : (
        <div className="card-image-placeholder" />
      )}
      <div className="card-title">{track.name}</div>
      <div className="card-subtitle">{track.artist.name}</div>
    </Link>
  );
}
