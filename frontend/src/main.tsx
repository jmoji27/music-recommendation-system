import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { AuthProvider } from "./context/AuthContext.tsx";
import { FriendsPanelProvider } from "./context/FriendsPanelContext.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FriendsPanelProvider>
          <App />
        </FriendsPanelProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
