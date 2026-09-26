import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ConversationSummary, MessageItem } from "../types";
import { timeAgo } from "../utils";
import { Avatar } from "../components/Avatar";
import { FriendsFeed } from "../components/FriendsFeed";
import { PeopleSearch } from "../components/PeopleSearch";

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
      {tab === "activity" && <FriendsFeed onFind={() => setTab("find")} />}
      {tab === "messages" && <MessagesTab />}
      {tab === "find" && <PeopleSearch />}
    </div>
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
