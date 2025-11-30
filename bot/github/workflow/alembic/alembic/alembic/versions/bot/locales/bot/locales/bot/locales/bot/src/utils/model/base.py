"""
SQLAlchemy base & session configuration.

We use the async engine with asyncpg.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.utils.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Create async engine with sslmode in DSN (recommended).
engine: AsyncEngine = create_async_engine(
    settings.POSTGRES_DSN,
    echo=False,  # Set True while debugging SQL
    future=True,
)

# Session factory to create AsyncSession objects.
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency-style generator that yields a DB session.

    'async with get_session() as session' can be used in handlers.
    """
    async with AsyncSessionLocal() as session:
        yield session
