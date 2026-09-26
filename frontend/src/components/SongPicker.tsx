import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { TrackSummary } from "../types";

const DEBOUNCE_MS = 350;

export function SongPicker({ onPick }: { onPick: (track: TrackSummary) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TrackSummary[] | null>(null);
  const [searching, setSearching] = useState(false);
  const latestRequest = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      return;
    }
    setSearching(true);
    const requestId = ++latestRequest.current;
    const timeout = setTimeout(async () => {
      try {
        const tracks = await api.get<TrackSummary[]>(`/catalog/tracks/search?q=${encodeURIComponent(trimmed)}`);
        // Ignore a slow response that's been superseded by a newer keystroke.
        if (requestId === latestRequest.current) setResults(tracks);
      } catch {
        if (requestId === latestRequest.current) setResults([]);
      } finally {
        if (requestId === latestRequest.current) setSearching(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [query]);

  return (
    <div className="song-picker">
      <input
        type="text"
        placeholder="Search for a song to recommend…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoFocus
      />
      {searching && <p className="muted">Searching…</p>}
      {results && results.length === 0 && !searching && <p className="muted">No songs found.</p>}
      <ul className="song-results">
        {results?.map((track) => (
          <li key={track.spotify_id}>
            <button type="button" className="song-result" onClick={() => onPick(track)}>
              <TrackArt track={track} />
              <span>
                <strong>{track.name}</strong>
                <span className="muted"> · {track.artist.name}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TrackArt({ track, size = 40 }: { track: TrackSummary; size?: number }) {
  const url = track.album?.image_url;
  return url ? (
    <img className="track-art" style={{ width: size, height: size }} src={url} alt="" />
  ) : (
    <span className="track-art track-art-empty" style={{ width: size, height: size }} />
  );
}
