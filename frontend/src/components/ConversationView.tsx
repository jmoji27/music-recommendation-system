import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { ConversationThread, MessageItem, TrackSummary } from "../types";
import { markSeen, timeAgo } from "../utils";
import { Avatar } from "./Avatar";
import { SongPicker } from "./SongPicker";
import { TrackChip } from "./TrackChip";

const POLL_MS = 4000;

interface Props {
  conversationId: number;
  /** Given: shows a back button (side panel). Omitted: links to /friends (full page). */
  onBack?: () => void;
}

/** A conversation thread + composer. Used both by the full /messages/:id
 *  page and inside the docked friends panel. */
export function ConversationView({ conversationId, onBack }: Props) {
  const { user } = useAuth();
  const [thread, setThread] = useState<ConversationThread | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [body, setBody] = useState("");
  const [track, setTrack] = useState<TrackSummary | null>(null);
  const [picking, setPicking] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const lastId = useRef(0);

  const base = `/conversations/${conversationId}/messages`;

  const append = useCallback(
    (incoming: MessageItem[]) => {
      if (incoming.length === 0) return;
      lastId.current = Math.max(lastId.current, ...incoming.map((m) => m.id));
      markSeen(conversationId, lastId.current);
      // De-dupe: a message we just sent can also arrive via the next poll.
      setMessages((current) => {
        const seen = new Set(current.map((m) => m.id));
        return [...current, ...incoming.filter((m) => !seen.has(m.id))];
      });
    },
    [conversationId],
  );

  useEffect(() => {
    api
      .get<ConversationThread>(base)
      .then((data) => {
        setThread(data);
        append(data.messages);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
      });
  }, [base, append]);

  // Simple polling for new messages; paused while the tab is hidden.
  useEffect(() => {
    if (!thread) return;
    const interval = setInterval(() => {
      if (document.hidden) return;
      api
        .get<ConversationThread>(`${base}?after_id=${lastId.current}`)
        .then((data) => append(data.messages))
        .catch(() => undefined);
    }, POLL_MS);
    return () => clearInterval(interval);
  }, [thread, base, append]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!body.trim() && !track) return;
    setSending(true);
    setError(null);
    try {
      const message = await api.post<MessageItem>(base, {
        body: body.trim() || null,
        track_spotify_id: track?.spotify_id ?? null,
      });
      append([message]);
      setBody("");
      setTrack(null);
      setPicking(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send. Try again.");
    } finally {
      setSending(false);
    }
  }

  if (notFound) return <p className="error">Conversation not found.</p>;
  if (!thread || !user) return <p className="muted">Loading…</p>;

  return (
    <div className="conversation-view">
      <header className="conversation-header">
        {onBack ? (
          <button className="link-button" onClick={onBack}>
            ← Back
          </button>
        ) : (
          <Link to="/friends">← Friends</Link>
        )}
        <Link to={`/users/${thread.with.id}`} className="person-link">
          <Avatar user={thread.with} size={32} /> <strong>{thread.with.display_name}</strong>
        </Link>
      </header>

      <div className="thread">
        {messages.map((message) => {
          const mine = message.sender_id === user.id;
          return (
            <div key={message.id} className={mine ? "bubble bubble-mine" : "bubble"}>
              {message.track && <TrackChip track={message.track} />}
              {message.body && <p>{message.body}</p>}
              <span className="muted bubble-time">{timeAgo(message.created_at)}</span>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={send}>
        {track && (
          <div className="composer-track">
            <TrackChip track={track} />
            <button type="button" onClick={() => setTrack(null)}>
              Remove
            </button>
          </div>
        )}
        {picking && !track && (
          <div className="composer-picker">
            <SongPicker
              onPick={(picked) => {
                setTrack(picked);
                setPicking(false);
              }}
            />
          </div>
        )}
        <div className="composer-row">
          <input
            type="text"
            placeholder="Write a message…"
            value={body}
            maxLength={2000}
            onChange={(event) => setBody(event.target.value)}
          />
          <button type="button" onClick={() => setPicking((v) => !v)} title="Recommend a song">
            🎵
          </button>
          <button className="button" type="submit" disabled={sending || (!body.trim() && !track)}>
            Send
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
