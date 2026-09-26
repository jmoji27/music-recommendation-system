"""Shared test fixtures.

Tests get their own engine with NullPool rather than reusing app.db's
pooled engine: pytest-asyncio gives each test function a fresh event loop
by default, and a pooled asyncpg connection created in one test's loop
can't be reused in another's ("attached to a different loop"). NullPool
opens a brand new physical connection per checkout, sidestepping that.

Each test runs inside an outer transaction that's always rolled back, with
the app's own `db.commit()` calls landing as SAVEPOINTs within it
(SQLAlchemy's `join_transaction_mode="create_savepoint"`) — so tests
exercise the real Postgres schema/constraints without leaving any data
behind, even though the endpoints under test call commit().
"""

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import get_db
from app.main import app

test_engine = create_async_engine(settings.database_url, poolclass=NullPool)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Limiter state is process-global; without this, one test's requests
    would count against the next test's budget."""
    from app import ratelimit

    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


@pytest.fixture(autouse=True)
def _provider_credentials(monkeypatch):
    """Login routes refuse to start without credentials; tests mock the
    provider's HTTP side, so any non-empty values will do."""
    monkeypatch.setattr(settings, "spotify_client_id", settings.spotify_client_id or "test-spotify-id")
    monkeypatch.setattr(settings, "spotify_client_secret", settings.spotify_client_secret or "test-spotify-secret")
    monkeypatch.setattr(settings, "google_client_id", settings.google_client_id or "test-google-id")
    monkeypatch.setattr(settings, "google_client_secret", settings.google_client_secret or "test-google-secret")


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.connect() as connection:
        trans = await connection.begin()
        # expire_on_commit=False to match app.db's real session factory —
        # otherwise tests enforce stricter behavior than production
        # actually has (objects expiring after commit here but not there).
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        yield session
        await session.close()
        await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def log_in_test_user(client, spotify_id: str = "spotify_test_user") -> None:
    """Drives the mocked OAuth login/callback so a test can act as an
    authenticated user without a real browser/Spotify consent screen.
    """
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fake-access-token",
                    "refresh_token": "fake-refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )
        mock.get("https://api.spotify.com/v1/me").mock(
            return_value=Response(
                200,
                json={"id": spotify_id, "display_name": "Test User", "email": f"{spotify_id}@example.com", "images": []},
            )
        )

        login_response = await client.get("/auth/spotify/login", follow_redirects=False)
        state = login_response.cookies["oauth_state"]
        callback_response = await client.get(
            "/auth/spotify/callback", params={"code": "fake-code", "state": state}, follow_redirects=False
        )
        # Redirects into the frontend now, rather than rendering a bare
        # confirmation page on the backend's own origin.
        assert callback_response.status_code == 302
        assert callback_response.headers["location"] == settings.frontend_origin
        assert "session" in callback_response.cookies
