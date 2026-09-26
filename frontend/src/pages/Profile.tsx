import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { FullProfile, HotAlbum, UserActivity, UserBrief } from "../types";
import { ActivityRow } from "../components/ActivityRow";
import { Avatar } from "../components/Avatar";
import { HotAlbumCard } from "../components/HotAlbumCard";
import { RecommendPanel } from "../components/RecommendPanel";

const MAX_AVATAR_BYTES = 200 * 1024;
const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"];

type Tab = "reviews" | "comments" | "likes";
type PeopleList = "followers" | "following" | null;

/** Serves both "/profile" (yours) and "/users/:userId" (anyone's). */
export function Profile() {
  const { userId } = useParams<{ userId: string }>();
  const { user, loading, refresh } = useAuth();

  const targetId = userId ? Number(userId) : user?.id;

  if (loading) return null;
  if (!userId && !user) return <Navigate to="/" replace />;
  if (targetId === undefined || Number.isNaN(targetId)) return <p className="error">User not found.</p>;

  return <ProfileView key={targetId} targetId={targetId} loggedIn={user !== null} refreshAuth={refresh} />;
}

function ProfileView({
  targetId,
  loggedIn,
  refreshAuth,
}: {
  targetId: number;
  loggedIn: boolean;
  refreshAuth: () => Promise<void>;
}) {
  const [profile, setProfile] = useState<FullProfile | null>(null);
  const [activity, setActivity] = useState<UserActivity | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<Tab>("reviews");
  const [people, setPeople] = useState<PeopleList>(null);
  const [peopleList, setPeopleList] = useState<UserBrief[] | null>(null);
  const [showRecommend, setShowRecommend] = useState(false);
  const [avatarVersion, setAvatarVersion] = useState(0);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([
        api.get<FullProfile>(`/users/${targetId}`),
        api.get<UserActivity>(`/users/${targetId}/activity`),
      ]);
      setProfile(p);
      setActivity(a);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
    }
  }, [targetId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!people) {
      setPeopleList(null);
      return;
    }
    api.get<UserBrief[]>(`/users/${targetId}/${people}`).then(setPeopleList);
  }, [people, targetId]);

  if (notFound) return <p className="error">User not found.</p>;
  if (!profile || !activity) return <p className="muted">Loading…</p>;

  async function toggleFollow() {
    if (!profile) return;
    if (profile.is_following) {
      await api.delete(`/users/${profile.id}/follow`);
      setShowRecommend(false);
    } else {
      await api.post(`/users/${profile.id}/follow`);
    }
    await load();
    if (people === "followers") setPeople(null);
  }

  async function uploadAvatar(file: File) {
    setAvatarError(null);
    if (!ALLOWED_TYPES.includes(file.type)) return setAvatarError("Use a PNG, JPEG or WebP image.");
    if (file.size > MAX_AVATAR_BYTES) return setAvatarError("That image is over 200KB — pick a smaller one.");
    try {
      await api.putFile("/me/avatar", file);
      setAvatarVersion(Date.now());
      await Promise.all([load(), refreshAuth()]);
    } catch (err) {
      setAvatarError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  async function removeAvatar() {
    await api.delete("/me/avatar");
    setAvatarVersion(Date.now());
    await Promise.all([load(), refreshAuth()]);
  }

  const hasCustomAvatar = profile.is_me && profile.avatar?.startsWith("/");
  const items = activity[tab];

  return (
    <div className="profile-page">
      <header className="profile-header">
        <Avatar user={profile} size={96} version={avatarVersion} />
        <div className="profile-info">
          {profile.is_me ? <NameEditor profile={profile} onSaved={async () => { await Promise.all([load(), refreshAuth()]); }} /> : <h1>{profile.display_name}</h1>}

          <div className="profile-stats">
            <button className="link-button" onClick={() => setPeople(people === "followers" ? null : "followers")}>
              <strong>{profile.follower_count}</strong> followers
            </button>
            <button className="link-button" onClick={() => setPeople(people === "following" ? null : "following")}>
              <strong>{profile.following_count}</strong> following
            </button>
            <span>
              <strong>{profile.review_count}</strong> reviews
            </span>
          </div>

          <div className="row-actions">
            {profile.is_me ? (
              <>
                <input
                  ref={fileInput}
                  type="file"
                  accept={ALLOWED_TYPES.join(",")}
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) uploadAvatar(file);
                    event.target.value = "";
                  }}
                />
                <button onClick={() => fileInput.current?.click()}>Change photo</button>
                {hasCustomAvatar && <button onClick={removeAvatar}>Use my Spotify/Google photo</button>}
              </>
            ) : (
              loggedIn && (
                <>
                  <button className={profile.is_following ? "" : "button"} onClick={toggleFollow}>
                    {profile.is_following ? "Following ✓" : "Follow"}
                  </button>
                  {profile.is_following && (
                    <button onClick={() => setShowRecommend((v) => !v)}>Recommend a song</button>
                  )}
                </>
              )
            )}
          </div>
          {avatarError && <p className="error">{avatarError}</p>}
          {!profile.is_me && loggedIn && !profile.is_following && (
            <p className="muted profile-hint">Follow {profile.display_name} to recommend them a song and start a conversation.</p>
          )}
        </div>
      </header>

      {showRecommend && <RecommendPanel toUserId={profile.id} toName={profile.display_name} />}

      {people && (
        <section className="people-list">
          <h2>{people === "followers" ? "Followers" : "Following"}</h2>
          {peopleList === null ? (
            <p className="muted">Loading…</p>
          ) : peopleList.length === 0 ? (
            <p className="muted">Nobody yet.</p>
          ) : (
            peopleList.map((person) => (
              <Link key={person.id} to={`/users/${person.id}`} className="person-row" onClick={() => setPeople(null)}>
                <Avatar user={person} size={36} /> {person.display_name}
              </Link>
            ))
          )}
        </section>
      )}

      {profile.is_me && <CommentIdeas />}

      <section>
        <div className="tabs">
          {(["reviews", "comments", "likes"] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? "tab active" : "tab"} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)} ({activity[t].length})
            </button>
          ))}
        </div>
        {items.length === 0 ? (
          <p className="muted">
            {profile.is_me ? `You haven't left any ${tab} yet.` : `No ${tab} yet.`}
          </p>
        ) : (
          items.map((item) => <ActivityRow key={`${item.type}-${item.id}`} item={item} />)
        )}
      </section>
    </div>
  );
}

function NameEditor({ profile, onSaved }: { profile: FullProfile; onSaved: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(profile.display_name);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setError(null);
    try {
      await api.patch("/me", { display_name: name });
      await onSaved();
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
  }

  if (!editing) {
    return (
      <h1>
        {profile.display_name}{" "}
        <button className="link-button" onClick={() => setEditing(true)}>
          Edit
        </button>
      </h1>
    );
  }
  return (
    <div className="name-editor">
      <input value={name} maxLength={50} onChange={(event) => setName(event.target.value)} autoFocus />
      <button className="button" onClick={save}>
        Save
      </button>
      <button onClick={() => setEditing(false)}>Cancel</button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/** Conversation starters: what people are reviewing right now. (A global
 *  Top-50 would be the obvious source, but Spotify doesn't expose charts
 *  to apps like this one — our own most-reviewed albums stand in.) */
function CommentIdeas() {
  const [albums, setAlbums] = useState<HotAlbum[] | null>(null);

  useEffect(() => {
    api.get<HotAlbum[]>("/hot-albums?limit=6").then(setAlbums);
  }, []);

  if (!albums || albums.length === 0) return null;
  return (
    <section className="comment-ideas">
      <h2>Not sure what to comment on?</h2>
      <p className="muted">These are getting the most reviews right now — jump into the conversation.</p>
      <div className="card-grid">
        {albums.map((album) => (
          <HotAlbumCard key={album.id} album={album} />
        ))}
      </div>
    </section>
  );
}
