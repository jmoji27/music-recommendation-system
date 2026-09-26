import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ActivityItem, ConversationSummary, MessageItem, UserSearchResult } from "../types";
import { timeAgo } from "../utils";
import { ActivityRow } from "../components/ActivityRow";
import { Avatar } from "../components/Avatar";

type Tab = "activity" | "messages" | "find";

export function Friends() {
  const [tab, setTab] = useState<Tab>("activity");

  return (
    <div className="friends-page">
      <h1>Friends</h1>
      <div className="tabs">
        <button className={tab === "activity" ? "tab active" : "tab"} onClick={() => setTab("activity")}>
          Activity
        </button>
        <button className={tab === "messages" ? "tab active" : "tab"} onClick={() => setTab("messages")}>
          Messages
        </button>
        <button className={tab === "find" ? "tab active" : "tab"} onClick={() => setTab("find")}>
          Find people
        </button>
      </div>
      {tab === "activity" && <FeedTab onFind={() => setTab("find")} />}
      {tab === "messages" && <MessagesTab />}
      {tab === "find" && <FindTab />}
    </div>
  );
}

function FeedTab({ onFind }: { onFind: () => void }) {
  const [feed, setFeed] = useState<ActivityItem[] | null>(null);

  useEffect(() => {
    api.get<ActivityItem[]>("/me/friends/feed").then(setFeed);
  }, []);

  if (feed === null) return <p className="muted">Loading…</p>;
  if (feed.length === 0) {
    return (
      <p className="muted">
        Nothing here yet. Follow some people to see their reviews, comments and likes —{" "}
        <button className="link-button" onClick={onFind}>
          find people
        </button>
        .
      </p>
    );
  }
  return (
    <>
      {feed.map((item) => (
        <ActivityRow key={`${item.type}-${item.id}`} item={item} />
      ))}
    </>
  );
}

function preview(message: MessageItem | null): string {
  if (!message) return "";
  if (message.track && !message.body) return `🎵 ${message.track.name} — ${message.track.artist.name}`;
  if (message.track) return `🎵 ${message.track.name} · ${message.body}`;
  return message.body ?? "";
}

function MessagesTab() {
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);

  useEffect(() => {
    api.get<ConversationSummary[]>("/conversations").then(setConversations);
  }, []);

  if (conversations === null) return <p className="muted">Loading…</p>;
  if (conversations.length === 0) {
    return (
      <p className="muted">
        No conversations yet. Open a friend's profile and recommend them a song to start one.
      </p>
    );
  }
  return (
    <div className="conversation-rows">
      {conversations.map((conversation) => (
        <Link key={conversation.id} to={`/messages/${conversation.id}`} className="person-row conversation-link">
          <Avatar user={conversation.with} size={44} />
          <span className="conversation-text">
            <strong>{conversation.with.display_name}</strong>
            <span className="muted conversation-preview-line">{preview(conversation.last_message)}</span>
          </span>
          <span className="muted">{timeAgo(conversation.last_message_at)}</span>
        </Link>
      ))}
    </div>
  );
}

const DEBOUNCE_MS = 300;

function FindTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearchResult[] | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      return;
    }
    const timeout = setTimeout(() => {
      api.get<UserSearchResult[]>(`/users/search?q=${encodeURIComponent(trimmed)}`).then(setResults);
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

  return (
    <div className="find-people">
      <input
        type="text"
        placeholder="Search people by name…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoFocus
      />
      {results && results.length === 0 && <p className="muted">Nobody found.</p>}
      {results?.map((person) => (
        <div key={person.id} className="person-row">
          <Link to={`/users/${person.id}`} className="person-link">
            <Avatar user={person} size={40} /> {person.display_name}
          </Link>
          <button className={person.is_following ? "" : "button"} onClick={() => toggle(person)}>
            {person.is_following ? "Following ✓" : "Follow"}
          </button>
        </div>
      ))}
    </div>
  );
}
