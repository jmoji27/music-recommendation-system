"""Login failures should land people back in the app with an explanation,
not on a raw JSON error page in the middle of an OAuth redirect chain."""

from fastapi.responses import RedirectResponse

from app.config import settings
from app.cookies import cookie_kwargs

# Reasons the frontend knows how to explain (see Landing in frontend/src).
NOT_CONFIGURED = "not_configured"  # this provider has no credentials set up on the server
EXPIRED = "expired"  # OAuth state missing/invalid/expired — start over
NOT_ALLOWLISTED = "not_allowlisted"  # Spotify Development Mode: account isn't on the tester list
FAILED = "failed"  # anything else the provider rejected


def login_error_redirect(provider: str, reason: str) -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.frontend_origin}/?login_error={reason}&provider={provider}", status_code=302
    )
    response.delete_cookie("oauth_state", **cookie_kwargs())
    return response
