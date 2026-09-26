import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Avatar } from "./Avatar";

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
            <Link to="/friends">Friends</Link>
            {user.has_spotify && <Link to="/taste">My Taste</Link>}
            <Link to="/profile" className="nav-profile">
              <Avatar user={{ display_name: user.display_name, avatar: user.avatar }} size={28} />
              <span className="nav-user">{user.display_name}</span>
            </Link>
            <button onClick={logout}>Log out</button>
          </>
        ) : (
          // Both providers are explained on the landing page — send
          // people there to choose, rather than picking one for them.
          <Link to="/">Log in</Link>
        )}
      </div>
    </nav>
  );
}
