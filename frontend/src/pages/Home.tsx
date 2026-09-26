import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, googleLoginUrl, spotifyLoginUrl } from "../api/client";
import type { AlbumConversation, AlbumSummary, ArtistCard as ArtistCardType, HotAlbum, TopTrackCard } from "../types";
import { AlbumCard } from "../components/AlbumCard";
import { TrackCard } from "../components/TrackCard";
import { ArtistCard } from "../components/ArtistCard";
import { ConversationCard } from "../components/ConversationCard";
import { HotAlbumCard } from "../components/HotAlbumCard";

export function Home() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (!user) return <Landing />;
  return <Dashboard hasSpotify={user.has_spotify} />;
}

const LOGIN_ERRORS: Record<string, string> = {
  not_configured: "That sign-in option isn't set up on this server yet.",
  expired: "Your sign-in link expired. Please try again.",
  not_allowlisted:
    "This Spotify account isn't on the tester list yet (Spotify limits how many accounts can connect). Try Google instead, or ask to be added.",
  failed: "Sign-in didn't complete. Please try again.",
};

function Landing() {
  const [params, setParams] = useSearchParams();
  const errorCode = params.get("login_error");
  const errorMessage = errorCode ? (LOGIN_ERRORS[errorCode] ?? LOGIN_ERRORS.failed) : null;
  const [providers, setProviders] = useState<{ spotify: boolean; google: boolean } | null>(null);

  useEffect(() => {
    api.get<{ spotify: boolean; google: boolean }>("/auth/providers").then(setProviders).catch(() => {});
  }, []);

  // Only hide a button once we positively know it's unconfigured.
  const spotifyOn = providers?.spotify ?? true;
  const googleOn = providers?.google ?? true;

  return (
    <div className="landing">
      {errorMessage && (
        <div className="login-error" role="alert">
          {errorMessage}{" "}
          <button className="link-button" onClick={() => setParams({}, { replace: true })}>
            Dismiss
          </button>
        </div>
      )}
      <h1>Understand your music taste.</h1>
      <p>
        Rate, review, and comment on music — and see what other people think of what you listen to.
      </p>

      <div className="login-choices">
        {spotifyOn && <div className="login-choice">
          <a className="button" href={spotifyLoginUrl}>
            Connect with Spotify
          </a>
          <p className="muted">
            Get personalized recommendations, your top tracks/artists/albums, and what you're
            currently listening to — based on your real Spotify taste.
          </p>
        </div>}
        {googleOn && <div className="login-choice">
          <a className="button button-secondary" href={googleLoginUrl}>
            Continue with Google
          </a>
          <p className="muted">
            Create an account to search, rate, review, and comment — no personalized
            recommendations though, since we won't have your listening data.
          </p>
        </div>}
      </div>
      <p className="muted login-note">
        Due to Spotify API limitations, only a small number of Spotify accounts can be connected
        right now — contact us if you'd like to try the Spotify-personalized demo.
      </p>

      <HotRightNow />
    </div>
  );
}

function HotRightNow() {
  const [hotAlbums, setHotAlbums] = useState<HotAlbum[] | null>(null);

  useEffect(() => {
    api.get<HotAlbum[]>("/hot-albums").then(setHotAlbums);
  }, []);

  if (!hotAlbums || hotAlbums.length === 0) return null;

  return (
    <section className="hot-section">
      <h2>Hot right now</h2>
      <div className="card-grid">
        {hotAlbums.map((album) => (
          <HotAlbumCard key={album.id} album={album} />
        ))}
      </div>
    </section>
  );
}

function Dashboard({ hasSpotify }: { hasSpotify: boolean }) {
  if (!hasSpotify) {
    return (
      <div className="dashboard">
        <section className="connect-prompt">
          <h2>Unlock your personalized recommendations</h2>
          <p className="muted">
            Connect Spotify to see your top tracks, artists, and albums.
          </p>
          <a className="button" href={spotifyLoginUrl}>
            Connect with Spotify
          </a>
        </section>
        <HotRightNow />
      </div>
    );
  }
  return <PersonalizedDashboard />;
}

function PersonalizedDashboard() {
  const [albums, setAlbums] = useState<AlbumSummary[] | null>(null);
  const [tracks, setTracks] = useState<TopTrackCard[] | null>(null);
  const [artists, setArtists] = useState<ArtistCardType[] | null>(null);
  const [conversations, setConversations] = useState<AlbumConversation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<AlbumSummary[]>("/me/top-albums"),
      api.get<TopTrackCard[]>("/me/top-tracks"),
      api.get<ArtistCardType[]>("/me/top-artists"),
      api.get<AlbumConversation[]>("/me/top-albums/conversations"),
    ])
      .then(([albumsRes, tracksRes, artistsRes, conversationsRes]) => {
        setAlbums(albumsRes);
        setTracks(tracksRes);
        setArtists(artistsRes);
        setConversations(conversationsRes);
      })
      .catch(() => setError("Couldn't load your Spotify data. Try refreshing."));
  }, []);

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="dashboard">
      <section>
        <h2>Conversations on your top albums</h2>
        {conversations === null ? (
          <p className="muted">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="muted">No reviews yet on albums you listen to — be the first to leave one.</p>
        ) : (
          <div className="conversation-list">
            {conversations.map((conversation) => (
              <ConversationCard key={conversation.spotify_album_id} conversation={conversation} />
            ))}
          </div>
        )}
      </section>

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
