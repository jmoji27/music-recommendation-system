import { assetUrl } from "../api/client";
import type { UserBrief } from "../types";

interface Props {
  user: Pick<UserBrief, "display_name" | "avatar">;
  size?: number;
  /** Bump to bypass the browser cache right after uploading a new picture. */
  version?: number;
}

export function Avatar({ user, size = 40, version }: Props) {
  const src = assetUrl(user.avatar);
  const url = src && version ? `${src}${src.includes("?") ? "&" : "?"}v=${version}` : src;
  const style = { width: size, height: size, fontSize: size * 0.42 };

  if (!url) {
    return (
      <span className="avatar avatar-fallback" style={style} aria-label={user.display_name}>
        {user.display_name.trim().charAt(0).toUpperCase() || "?"}
      </span>
    );
  }
  return <img className="avatar" style={style} src={url} alt={user.display_name} />;
}
