export interface UserProfile {
  id: number;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  avatar: string | null;
  has_spotify: boolean;
}

export interface UserBrief {
  id: number;
  display_name: string;
  avatar: string | null;
}

export interface FullProfile extends UserBrief {
  follower_count: number;
  following_count: number;
  review_count: number;
  is_following: boolean;
  is_me: boolean;
  /** True when you've blocked them; the server then sends only the name/avatar, no counts. */
  blocked_by_me?: boolean;
  joined_at: string;
}

export interface UserSearchResult extends UserBrief {
  is_following: boolean;
}

export interface ActivityItem {
  id: number;
  type: "review" | "comment" | "like";
  created_at: string;
  actor?: UserBrief;
  album: AlbumSummary | null;
  stars?: number | null;
  content?: string | null;
  review_id?: number;
  review_author?: UserBrief;
  target_type?: "review" | "comment";
  target_excerpt?: string | null;
  target_author?: UserBrief;
}

export interface UserActivity {
  reviews: ActivityItem[];
  comments: ActivityItem[];
  likes: ActivityItem[];
}

export interface TrackSummary {
  id: number;
  spotify_id: string;
  name: string;
  duration_ms: number | null;
  artist: { id: number; name: string };
  album: { id: number; spotify_id: string; name: string; image_url: string | null } | null;
}

export interface MessageItem {
  id: number;
  sender_id: number;
  body: string | null;
  track: TrackSummary | null;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  with: UserBrief;
  last_message: MessageItem | null;
  last_message_at: string;
}

export interface ConversationThread {
  conversation_id: number;
  with: UserBrief;
  messages: MessageItem[];
}

export interface ArtistRef {
  id: number;
  spotify_id?: string;
  name: string;
}

export interface AlbumSummary {
  id: number;
  spotify_id: string;
  name: string;
  release_date: string | null;
  image_url: string | null;
  artist: ArtistRef;
}

export interface AlbumDetail extends AlbumSummary {
  tracks: TrackRef[];
}

export interface TrackRef {
  id: number;
  spotify_id: string;
  name: string;
  duration_ms: number | null;
}

export interface TopTrackCard {
  id: number;
  spotify_id: string;
  name: string;
  duration_ms: number | null;
  album: { id: number; name: string; image_url: string | null };
  artist: ArtistRef;
}

export interface ArtistCard {
  id: number;
  spotify_id: string;
  name: string;
  genres: string[];
  image_url: string | null;
}

export interface CommentItem {
  edited: boolean;
  liked_by_me: boolean;
  id: number;
  content: string;
  created_at: string;
  user: { id: number; display_name: string };
  like_count: number;
}

export interface ReviewItem {
  edited: boolean;
  liked_by_me: boolean;
  id: number;
  stars: number | null;
  content: string | null;
  created_at: string;
  user: { id: number; display_name: string };
  like_count: number;
  comments: CommentItem[];
}

export interface HotAlbum extends AlbumSummary {
  review_count: number;
}

export interface AlbumConversation {
  spotify_album_id: string;
  album: AlbumSummary;
  reviews: ReviewItem[];
}

export interface TasteSummary {
  genre_counts: Record<string, number>;
  top_genre: string | null;
  recent_minutes_listened: number;
  recent_track_count: number;
  top_artist_names: string[];
}

export type TasteRecommendation =
  | { available: false; reason: "not_configured" | "error" }
  | { available: true; summary: string; recommended_genres: string[]; recommended_artists: string[] };
