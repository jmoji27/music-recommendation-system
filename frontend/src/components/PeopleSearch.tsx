import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { UserSearchResult } from "../types";
import { Avatar } from "./Avatar";

const DEBOUNCE_MS = 300;

interface Props {
  /** When given, people you follow get a button that calls this (e.g. to
   *  start a conversation by recommending them a song). */
  onMessage?: (person: UserSearchResult) => void;
  compact?: boolean;
}

export function PeopleSearch({ onMessage, compact }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchResult[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      return;
    }
    const timeout = setTimeout(() => {
      setFailed(false);
      api
        .get<UserSearchResult[]>(`/users/search?q=${encodeURIComponent(trimmed)}`)
        .then(setResults)
        .catch(() => setFailed(true));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [query]);

  async function toggle(person: UserSearchResult) {
    if (person.is_following) await api.delete(`/users/${person.id}/follow`);
    else await api.post(`/users/${person.id}/follow`);
    setResults((current) =>
      current ? current.map((r) => (r.id === person.id ? { ...r, is_following: !r.is_following } : r)) : current,
    );
  }

  async function block(person: UserSearchResult) {
    if (!window.confirm(`Block ${person.display_name}? They won't be able to see or contact you.`)) return;
    await api.post(`/users/${person.id}/block`);
    setResults((current) => (current ? current.filter((r) => r.id !== person.id) : current));
  }

  return (
    <div className={compact ? "find-people find-people-compact" : "find-people"}>
      <input
        type="text"
        placeholder="Search people by name…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoFocus
      />
      {failed && <p className="error">Search failed — try again.</p>}
      {results && results.length === 0 && <p className="muted">Nobody found.</p>}
      {results?.map((person) => (
        <div key={person.id} className="person-row">
          <Link to={`/users/${person.id}`} className="person-link">
            <Avatar user={person} size={compact ? 32 : 40} /> {person.display_name}
          </Link>
          <span className="person-actions">
            {person.is_following && onMessage && (
              <button onClick={() => onMessage(person)} title="Recommend a song to start a chat">
                🎵
              </button>
            )}
            <button className={person.is_following ? "" : "button"} onClick={() => toggle(person)}>
              {person.is_following ? "Following ✓" : "Follow"}
            </button>
            <button onClick={() => block(person)} title="Block this person" aria-label={`Block ${person.display_name}`}>
              🚫
            </button>
          </span>
        </div>
      ))}
    </div>
  );
}
