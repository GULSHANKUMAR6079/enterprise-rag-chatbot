"""
Database Session Management.
Supports async PostgreSQL (asyncpg) for production and SQLite (aiosqlite) for offline/testing.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

# Engine configuration with connection pooling and timeouts
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    # SQLite does not support standard pool size kwargs
    engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_timeout=30,
        **engine_kwargs
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
