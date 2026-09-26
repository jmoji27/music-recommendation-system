import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "./AuthContext";

const OPEN_KEY = "friends-panel-open";

interface PanelState {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

const FriendsPanelContext = createContext<PanelState | null>(null);

function defaultOpen(): boolean {
  try {
    const stored = localStorage.getItem(OPEN_KEY);
    if (stored !== null) return stored === "1";
  } catch {
    // fall through to the viewport-based default
  }
  return window.innerWidth >= 1100;
}

/** Owns whether the friends panel is open, so both the panel itself and the
 *  nav's "Friends" button can control it. Also reserves layout space beside
 *  the page — but only while someone is logged in, since logged-out visitors
 *  never see the panel. */
export function FriendsPanelProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(defaultOpen);
  const loggedIn = user !== null;

  useEffect(() => {
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch {
      // not persisting is fine
    }
  }, [open]);

  useEffect(() => {
    document.body.classList.toggle("panel-open", open && loggedIn);
    return () => document.body.classList.remove("panel-open");
  }, [open, loggedIn]);

  const toggle = useCallback(() => setOpen((current) => !current), []);

  return <FriendsPanelContext.Provider value={{ open, setOpen, toggle }}>{children}</FriendsPanelContext.Provider>;
}

export function useFriendsPanel(): PanelState {
  const context = useContext(FriendsPanelContext);
  if (!context) throw new Error("useFriendsPanel must be used within a FriendsPanelProvider");
  return context;
}
