export interface UserProfile {
  id: number;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
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
  id: number;
  content: string;
  created_at: string;
  user: { id: number; display_name: string };
  like_count: number;
}

export interface ReviewItem {
  id: number;
  stars: number | null;
  content: string | null;
  created_at: string;
  user: { id: number; display_name: string };
  like_count: number;
  comments: CommentItem[];
}
