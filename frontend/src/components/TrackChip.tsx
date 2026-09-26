import { Link } from "react-router-dom";
import type { TrackSummary } from "../types";
import { TrackArt } from "./SongPicker";

export function TrackChip({ track }: { track: TrackSummary }) {
  const content = (
    <>
      <TrackArt track={track} size={48} />
      <span className="track-chip-text">
        <strong>{track.name}</strong>
        <span className="muted">{track.artist.name}</span>
      </span>
    </>
  );
  return track.album ? (
    <Link to={`/albums/${track.album.spotify_id}`} className="track-chip">
      {content}
    </Link>
  ) : (
    <div className="track-chip">{content}</div>
  );
}
