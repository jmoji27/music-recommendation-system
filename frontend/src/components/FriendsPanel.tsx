import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useFriendsPanel } from "../context/FriendsPanelContext";
import type { ConversationSummary, MessageItem, UserSearchResult } from "../types";
import { getSeen, SEEN_EVENT, timeAgo } from "../utils";
import { Avatar } from "./Avatar";
import { FriendsFeed } from "./FriendsFeed";
import { ConversationView } from "./ConversationView";
import { PeopleSearch } from "./PeopleSearch";
import { RecommendPanel } from "./RecommendPanel";

const LIST_POLL_MS = 10000;

type View =
  | { kind: "list" }
  | { kind: "thread"; id: number }
  | { kind: "compose"; person: UserSearchResult };
type Tab = "messages" | "activity" | "add";

function preview(message: MessageItem | null): string {
  if (!message) return "";
  if (message.track && !message.body) return `🎵 ${message.track.name} — ${message.track.artist.name}`;
  if (message.track) return `🎵 ${message.track.name} · ${message.body}`;
  return message.body ?? "";
}

/** A docked side panel that stays on every page: your conversations, plus a
 *  way to find and add people. Opening a chat happens inside the panel. */
export function FriendsPanel() {
  const { user } = useAuth();
  const { open, setOpen } = useFriendsPanel();
  const [tab, setTab] = useState<Tab>("messages");
  const [view, setView] = useState<View>({ kind: "list" });
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [, forceRender] = useState(0);

  const loadConversations = useCallback(() => {
    api
      .get<ConversationSummary[]>("/conversations")
      .then((list) => {
        setConversations(list);
        setLoaded(true);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    loadConversations();
    const interval = setInterval(() => {
      if (!document.hidden) loadConversations();
    }, LIST_POLL_MS);
    return () => clearInterval(interval);
  }, [loadConversations]);

  // Re-render when a thread marks messages seen, so unread dots clear at once.
  useEffect(() => {
    const onSeen = () => forceRender((n) => n + 1);
    window.addEventListener(SEEN_EVENT, onSeen);
    return () => window.removeEventListener(SEEN_EVENT, onSeen);
  }, []);

  if (!user) return null;

  const isUnread = (c: ConversationSummary) =>
    c.last_message !== null && c.last_message.sender_id !== user.id && c.last_message.id > getSeen(c.id);
  const unreadCount = conversations.filter(isUnread).length;

  function backToList() {
    setView({ kind: "list" });
    loadConversations();
  }

  if (!open) {
    return (
      <button className="friends-tab" onClick={() => setOpen(true)} aria-label="Open friends panel">
        💬 Friends
        {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
      </button>
    );
  }

  return (
    <aside className="friends-panel" aria-label="Friends and messages">
      <header className="panel-header">
        <strong>Friends</strong>
        <button className="link-button" onClick={() => setOpen(false)} aria-label="Collapse friends panel">
          Hide ›
        </button>
      </header>

      {view.kind === "thread" && (
        <div className="panel-body">
          <ConversationView key={view.id} conversationId={view.id} onBack={backToList} />
        </div>
      )}

      {view.kind === "compose" && (
        <div className="panel-body">
          <button className="link-button" onClick={backToList}>
            ← Back
          </button>
          <RecommendPanel
            toUserId={view.person.id}
            toName={view.person.display_name}
            onStarted={(id) => {
              loadConversations();
              setView({ kind: "thread", id });
            }}
          />
        </div>
      )}

      {view.kind === "list" && (
        <>
          <div className="tabs panel-tabs">
            <button className={tab === "messages" ? "tab active" : "tab"} onClick={() => setTab("messages")}>
              Messages{unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
            </button>
            <button className={tab === "activity" ? "tab active" : "tab"} onClick={() => setTab("activity")}>
              Activity
            </button>
            <button className={tab === "add" ? "tab active" : "tab"} onClick={() => setTab("add")}>
              Add people
            </button>
          </div>

          <div className="panel-body">
            {tab === "messages" &&
              (!loaded ? (
                <p className="muted">Loading…</p>
              ) : conversations.length === 0 ? (
                <p className="muted">
                  No conversations yet.{" "}
                  <button className="link-button" onClick={() => setTab("add")}>
                    Add someone
                  </button>{" "}
                  and recommend them a song to start one.
                </p>
              ) : (
                conversations.map((conversation) => {
                  const unread = isUnread(conversation);
                  return (
                    <button
                      key={conversation.id}
                      className={unread ? "panel-conversation unread" : "panel-conversation"}
                      onClick={() => setView({ kind: "thread", id: conversation.id })}
                    >
                      <Avatar user={conversation.with} size={36} />
                      <span className="conversation-text">
                        <strong>{conversation.with.display_name}</strong>
                        <span className="muted conversation-preview-line">{preview(conversation.last_message)}</span>
                      </span>
                      <span className="panel-meta">
                        <span className="muted">{timeAgo(conversation.last_message_at)}</span>
                        {unread && <span className="unread-dot" aria-label="Unread" />}
                      </span>
                    </button>
                  );
                })
              ))}

            {tab === "activity" && <FriendsFeed onFind={() => setTab("add")} />}

            {tab === "add" && (
              <PeopleSearch compact onMessage={(person) => setView({ kind: "compose", person })} />
            )}
          </div>
        </>
      )}
    </aside>
  );
}
