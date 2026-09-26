import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { TrackSummary } from "../types";
import { SongPicker } from "./SongPicker";
import { TrackChip } from "./TrackChip";

/** Starting a conversation means recommending a song — that's the whole
 *  rule, so this panel is the only way in. */
export function RecommendPanel({ toUserId, toName }: { toUserId: number; toName: string }) {
  const navigate = useNavigate();
  const [track, setTrack] = useState<TrackSummary | null>(null);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    if (!track) return;
    setSending(true);
    setError(null);
    try {
      const result = await api.post<{ conversation_id: number }>("/conversations", {
        to_user_id: toUserId,
        track_spotify_id: track.spotify_id,
        body: body.trim() || null,
      });
      navigate(`/messages/${result.conversation_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send. Try again.");
      setSending(false);
    }
  }

  return (
    <div className="recommend-panel">
      <h3>Recommend a song to {toName}</h3>
      {track ? (
        <>
          <TrackChip track={track} />
          <textarea
            placeholder={`Say something about it (optional)…`}
            value={body}
            maxLength={2000}
            onChange={(event) => setBody(event.target.value)}
          />
          <div className="row-actions">
            <button className="button" onClick={send} disabled={sending}>
              {sending ? "Sending…" : "Send recommendation"}
            </button>
            <button onClick={() => setTrack(null)} disabled={sending}>
              Pick a different song
            </button>
          </div>
        </>
      ) : (
        <SongPicker onPick={setTrack} />
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
