import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { loginUrl } from "../api/client";

export function Nav() {
  const { user, loading, logout } = useAuth();

  return (
    <nav className="nav">
      <Link to="/" className="nav-brand">
        Music Rec
      </Link>
      <div className="nav-links">
        <Link to="/search">Search</Link>
        {loading ? null : user ? (
          <>
            <span className="nav-user">{user.display_name}</span>
            <button onClick={logout}>Log out</button>
          </>
        ) : (
          <a href={loginUrl}>Connect with Spotify</a>
        )}
      </div>
    </nav>
  );
}
