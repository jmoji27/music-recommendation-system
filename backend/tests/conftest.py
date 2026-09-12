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

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import get_db
from app.main import app

test_engine = create_async_engine(settings.database_url, poolclass=NullPool)


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
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
