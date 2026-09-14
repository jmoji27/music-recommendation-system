import { Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Home } from "./pages/Home";
import { Search } from "./pages/Search";
import { AlbumDetail } from "./pages/AlbumDetail";
import { Taste } from "./pages/Taste";

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
        </Routes>
      </main>
    </>
  );
}

export default App;
