import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import { api, loginUrl } from "../api/client";
import type { AlbumSummary, ArtistCard as ArtistCardType, TopTrackCard } from "../types";
import { AlbumCard } from "../components/AlbumCard";
import { TrackCard } from "../components/TrackCard";
import { ArtistCard } from "../components/ArtistCard";

export function Home() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (!user) return <Landing />;
  return <Dashboard />;
}

function Landing() {
  return (
    <div className="landing">
      <h1>Understand your music taste.</h1>
      <p>
        Connect Spotify to see your top tracks, artists, and albums — and start rating, reviewing, and
        comparing taste with others.
      </p>
      <a className="button" href={loginUrl}>
        Connect with Spotify
      </a>
    </div>
  );
}

function Dashboard() {
  const [albums, setAlbums] = useState<AlbumSummary[] | null>(null);
  const [tracks, setTracks] = useState<TopTrackCard[] | null>(null);
  const [artists, setArtists] = useState<ArtistCardType[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<AlbumSummary[]>("/me/top-albums"),
      api.get<TopTrackCard[]>("/me/top-tracks"),
      api.get<ArtistCardType[]>("/me/top-artists"),
    ])
      .then(([albumsRes, tracksRes, artistsRes]) => {
        setAlbums(albumsRes);
        setTracks(tracksRes);
        setArtists(artistsRes);
      })
      .catch(() => setError("Couldn't load your Spotify data. Try refreshing."));
  }, []);

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="dashboard">
      <Section title="Your top albums" empty="No albums yet — keep listening on Spotify." items={albums}>
        {(album) => <AlbumCard key={album.id} album={album} />}
      </Section>

      <Section title="Your top tracks" empty="No tracks yet." items={tracks}>
        {(track) => <TrackCard key={track.id} track={track} />}
      </Section>

      <Section title="Your top artists" empty="No artists yet." items={artists}>
        {(artist) => <ArtistCard key={artist.id} artist={artist} />}
      </Section>
    </div>
  );
}

function Section<T>({
  title,
  empty,
  items,
  children,
}: {
  title: string;
  empty: string;
  items: T[] | null;
  children: (item: T) => ReactNode;
}) {
  return (
    <section>
      <h2>{title}</h2>
      {items === null ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <div className="card-grid">{items.map(children)}</div>
      )}
    </section>
  );
}
