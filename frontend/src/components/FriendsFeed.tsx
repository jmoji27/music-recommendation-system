import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ActivityItem } from "../types";
import { ActivityRow } from "./ActivityRow";

/** Recent reviews/comments/likes from people you follow. */
export function FriendsFeed({ onFind }: { onFind: () => void }) {
  const [feed, setFeed] = useState<ActivityItem[] | null>(null);

  useEffect(() => {
    api
      .get<ActivityItem[]>("/me/friends/feed")
      .then(setFeed)
      .catch(() => setFeed([]));
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
