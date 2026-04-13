"""SQLAlchemy async engine and session factory.

Persistence boundary:
  - All Foundation (and future domain) CRUD uses these sessions.
  - Legacy admin/migration endpoints use raw asyncpg via backend/db.py.
  - New domain CRUD should use get_db() unless explicitly justified.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.async_database_url,
    echo=(settings.environment == "development"),
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
