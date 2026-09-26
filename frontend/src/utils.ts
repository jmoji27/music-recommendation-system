export function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Unread tracking ─────────────────────────────────────────────────────
// Purely client-side: the backend doesn't track read state, so each browser
// remembers the newest message id it has shown per conversation. That means
// unread dots don't sync across devices — an accepted limitation for now.

const SEEN_KEY = "conversation-seen-v1";
export const SEEN_EVENT = "conversation-seen-changed";

function readSeen(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(SEEN_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function getSeen(conversationId: number): number {
  return readSeen()[String(conversationId)] ?? 0;
}

export function markSeen(conversationId: number, messageId: number): void {
  if (getSeen(conversationId) >= messageId) return;
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify({ ...readSeen(), [conversationId]: messageId }));
  } catch {
    return; // storage blocked (private mode etc.): unread dots just won't clear
  }
  window.dispatchEvent(new Event(SEEN_EVENT));
}
