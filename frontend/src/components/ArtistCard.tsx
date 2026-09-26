import { Link } from "react-router-dom";
import type { ArtistCard as ArtistCardType } from "../types";

export function ArtistCard({ artist }: { artist: ArtistCardType }) {
  return (
    <Link to={`/search?q=${encodeURIComponent(artist.name)}`} className="card" title={`Find ${artist.name} albums`}>
      {artist.image_url ? (
        <img src={artist.image_url} alt={artist.name} />
      ) : (
        <div className="card-image-placeholder" />
      )}
      <div className="card-title">{artist.name}</div>
      <div className="card-subtitle">{artist.genres.slice(0, 2).join(", ")}</div>
    </Link>
  );
}
