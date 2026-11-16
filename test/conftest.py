from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.entities.base import Base
from app.db.entities.candidate import Candidate  # noqa: F401
from app.db.entities.event_outbox import EventOutbox  # noqa: F401 — registers with Base.metadata
from app.db.entities.node import Node  # noqa: F401
from app.db.entities.user import User  # noqa: F401
from app.service.storage.base import AsyncStorageService, StoredObject


class StubStorageService(AsyncStorageService):
    """In-memory storage stub that records stored objects without any I/O."""

    def __init__(self) -> None:
        self.stored: dict[str, StoredObject] = {}
        self._counter = 0

    async def store(self, document: StoredObject) -> str:
        self._counter += 1
        storage_id = f"stub-storage-{self._counter}"
        self.stored[storage_id] = document
        return storage_id

    async def remove(self, id: str) -> None:
        self.stored.pop(id, None)

    async def load(self, id: str) -> StoredObject:
        return self.stored[id]


@pytest.fixture
async def db_sess():
    """
    Provides a fresh SQLite in-memory AsyncSession for each test.

    Setup:  creates all tables.
    Teardown: drops all tables and disposes the engine so the
              in-memory database is fully discarded.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
def storage_service() -> StubStorageService:
    return StubStorageService()


@pytest.fixture
def patch_get_db_sess(db_sess: AsyncSession):
    """Patch get_db_sess in document service to yield the test db session."""

    @asynccontextmanager
    async def _mock():
        yield db_sess

    with patch("app.service.document.get_db_sess", _mock):
        yield
