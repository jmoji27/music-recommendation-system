import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { AlbumSummary } from "../types";
import { AlbumCard } from "../components/AlbumCard";

const DEBOUNCE_MS = 350;

export function Search() {
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [results, setResults] = useState<AlbumSummary[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      return;
    }

    setSearching(true);
    const timeoutId = setTimeout(async () => {
      try {
        const albums = await api.get<AlbumSummary[]>(`/catalog/albums/search?q=${encodeURIComponent(trimmed)}`);
        setResults(albums);
      } finally {
        setSearching(false);
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timeoutId);
  }, [query]);

  return (
    <div className="search-page">
      <input
        type="text"
        placeholder="Search albums…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoFocus
      />
      {searching && <p className="muted">Searching…</p>}
      {results && (
        <div className="card-grid">
          {results.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      )}
    </div>
  );
}
