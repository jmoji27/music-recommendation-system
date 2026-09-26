import { Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Home } from "./pages/Home";
import { Search } from "./pages/Search";
import { AlbumDetail } from "./pages/AlbumDetail";
import { Taste } from "./pages/Taste";
import { Friends } from "./pages/Friends";
import { Conversation } from "./pages/Conversation";
import { Profile } from "./pages/Profile";
import { RequireAuth } from "./components/RequireAuth";

function App() {
  return (
    <>
      <Nav />
      <main className="container">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/albums/:spotifyId" element={<AlbumDetail />} />
          <Route path="/taste" element={<Taste />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/users/:userId" element={<Profile />} />
          <Route
            path="/friends"
            element={
              <RequireAuth>
                <Friends />
              </RequireAuth>
            }
          />
          <Route
            path="/messages/:conversationId"
            element={
              <RequireAuth>
                <Conversation />
              </RequireAuth>
            }
          />
        </Routes>
      </main>
    </>
  );
}

export default App;
