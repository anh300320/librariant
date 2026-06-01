from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.entities.base import Base
from app.db.entities.node import Node  # noqa: F401
from app.db.entities.user import User  # noqa: F401
from app.settings.database import database_settings

engine: AsyncEngine = create_async_engine(
    database_settings.url,
    echo=False,
    pool_size=database_settings.pool_size,
    max_overflow=database_settings.max_overflow,
    pool_timeout=database_settings.pool_timeout,
    pool_recycle=database_settings.pool_recycle,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_sess() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
