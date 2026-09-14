"""Cookie flags that differ between local dev and production.

Locally, frontend and backend are different ports on the same host
(127.0.0.1) — same-site, so SameSite=Lax works fine, and there's no
HTTPS to require Secure. Deployed on free subdomains, frontend and
backend are on genuinely different domains — cross-site — so the
cookie needs SameSite=None (which browsers only honor when Secure is
also set, hence the pairing below).
"""

from app.config import settings


def cookie_kwargs() -> dict:
    if settings.is_production:
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}
