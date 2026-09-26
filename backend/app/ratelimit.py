"""In-memory sliding-window rate limiting.

Safe by default: `baseline_limit` is installed app-wide, so every route —
including ones added later — has a ceiling without anyone remembering to
opt in. Expensive or abusable routes add a stricter named limit on top
(see the instances at the bottom).

Keyed by user id when the request carries a valid session, otherwise by
client IP. Two honest limits of this implementation:
- State is per-process. Fine for a single-worker deploy; with several
  workers each gets its own counters (use Redis if that ever matters).
- Behind a reverse proxy, every anonymous visitor shares the proxy's IP
  unless uvicorn runs with --proxy-headers and the proxy is trusted
  (--forwarded-allow-ips). Logged-in users are unaffected (keyed by id).
"""

import time
from collections import deque

from fastapi import HTTPException, Request, status
from jose import JWTError

from app.config import settings
from app.security import decode_session_token

_hits: dict[str, deque[float]] = {}
_MAX_KEYS = 20_000  # bound memory: purge idle keys past this


def reset_all() -> None:
    """For tests."""
    _hits.clear()


def _identity(request: Request) -> str:
    token = request.cookies.get("session")
    if token:
        try:
            return f"user:{decode_session_token(token)['user_id']}"
        except JWTError:
            pass
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _purge_idle(now: float, longest_window: float) -> None:
    for key in [k for k, v in _hits.items() if not v or now - v[-1] > longest_window]:
        del _hits[key]


class RateLimiter:
    def __init__(self, name: str, limit: int, window_seconds: int, *, methods: set[str] | None = None):
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self.methods = methods  # None = every method

    async def __call__(self, request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        if self.methods is not None and request.method not in self.methods:
            return

        now = time.monotonic()
        if len(_hits) > _MAX_KEYS:
            _purge_idle(now, longest_window=3600)

        key = f"{self.name}:{_identity(request)}"
        window = _hits.setdefault(key, deque())
        while window and now - window[0] > self.window:
            window.popleft()

        if len(window) >= self.limit:
            retry_after = max(1, int(self.window - (now - window[0])) + 1)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests — slow down and try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)


_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

# App-wide ceilings (installed in main.py).
baseline_reads = RateLimiter("read", 600, 60, methods={"GET"})
baseline_writes = RateLimiter("write", 90, 60, methods=_UNSAFE)

# Routes that hit paid/quota'd upstreams (Spotify, Gemini) or are easy to abuse.
catalog_limit = RateLimiter("catalog", 40, 60)  # each miss is a live Spotify call
gemini_limit = RateLimiter("gemini", 6, 60)  # free tier is ~20 calls/DAY
auth_limit = RateLimiter("auth", 20, 60)  # login/callback
start_conversation_limit = RateLimiter("start-conversation", 20, 3600)
avatar_limit = RateLimiter("avatar", 10, 3600)
follow_limit = RateLimiter("follow", 60, 60)
