import { Link } from "react-router-dom";
import type { ActivityItem } from "../types";
import { timeAgo } from "../utils";
import { Avatar } from "./Avatar";

function AlbumLink({ item }: { item: ActivityItem }) {
  if (!item.album) return <>an album</>;
  return (
    <Link to={`/albums/${item.album.spotify_id}`}>
      {item.album.name} <span className="muted">by {item.album.artist.name}</span>
    </Link>
  );
}

function Who({ item }: { item: ActivityItem }) {
  return item.actor ? <Link to={`/users/${item.actor.id}`}>{item.actor.display_name}</Link> : <>You</>;
}

/** One line of "someone did something" — used in the friends feed (with
 *  the actor) and on profiles (actor omitted, it's implied). */
export function ActivityRow({ item }: { item: ActivityItem }) {
  // "jakov liked jakov's review" reads oddly — say "their own" instead.
  const ownerOf = (author?: { id: number; display_name: string }) =>
    item.actor && author && author.id === item.actor.id ? "their own" : `${author?.display_name}'s`;

  return (
    <div className="activity-row">
      {item.actor && <Avatar user={item.actor} size={36} />}
      <div className="activity-body">
        <div>
          {item.actor && <Who item={item} />}
          {item.type === "review" && (
            <>
              {item.actor ? " reviewed " : "Reviewed "}
              <AlbumLink item={item} />
              {item.stars ? <span className="stars"> {"★".repeat(item.stars)}</span> : null}
            </>
          )}
          {item.type === "comment" && (
            <>
              {item.actor ? " commented on " : "Commented on "}
              {ownerOf(item.review_author)} review of <AlbumLink item={item} />
            </>
          )}
          {item.type === "like" && (
            <>
              {item.actor ? " liked " : "Liked "}
              {ownerOf(item.target_author)} {item.target_type} on <AlbumLink item={item} />
            </>
          )}
        </div>
        {(item.content || item.target_excerpt) && <p className="activity-quote">{item.content ?? item.target_excerpt}</p>}
        <div className="muted activity-time">{timeAgo(item.created_at)}</div>
      </div>
    </div>
  );
}
