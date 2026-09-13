import type { TopTrackCard } from "../types";

export function TrackCard({ track }: { track: TopTrackCard }) {
  return (
    <div className="card">
      {track.album.image_url ? (
        <img src={track.album.image_url} alt={track.album.name} />
      ) : (
        <div className="card-image-placeholder" />
      )}
      <div className="card-title">{track.name}</div>
      <div className="card-subtitle">{track.artist.name}</div>
    </div>
  );
}
