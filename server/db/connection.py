"""Async database connection pool with OAuth token refresh."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import time
import logging

from server.auth.databricks import get_databricks_oauth_token
from server.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """
    Database connection pool with automatic OAuth token refresh.

    Refreshes Databricks OAuth token every 15 minutes to prevent connection failures.
    """

    def __init__(self):
        self._engine = None
        self._session_maker = None
        self._last_token_refresh = 0
        self._refresh_interval = 900  # 15 minutes in seconds

    async def _get_connection_url(self) -> str:
        """
        Get database connection URL with fresh OAuth token.

        Refreshes token if more than 15 minutes have elapsed.
        """
        current_time = time.time()

        if current_time - self._last_token_refresh > self._refresh_interval:
            logger.info("Refreshing Databricks OAuth token for database connection")
            token = await get_databricks_oauth_token()
            settings = get_settings()

            connection_url = (
                f"postgresql+asyncpg://{settings.pguser}:{token}@"
                f"{settings.pghost}:{settings.pgport}/{settings.pgdatabase}"
            )

            # Recreate engine with new token
            if self._engine:
                await self._engine.dispose()

            self._engine = create_async_engine(
                connection_url,
                poolclass=NullPool,  # Disable pooling to allow token refresh
                echo=False,
                connect_args={"ssl": "require"},  # Enable SSL for prod databases
            )

            self._session_maker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            self._last_token_refresh = current_time

        return self._engine

    async def get_session(self) -> AsyncSession:
        """Get a database session with fresh connection."""
        await self._get_connection_url()
        return self._session_maker()

    async def dispose(self):
        """Dispose of the connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None


# Global connection pool instance
_connection_pool = DatabaseConnectionPool()


async def get_db_session() -> AsyncSession:
    """
    Get an async database session.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    return await _connection_pool.get_session()


@asynccontextmanager
async def get_db_context():
    """
    Context manager for database sessions.

    Automatically commits on success and rolls back on exceptions.
    """
    session = await get_db_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_connection_pool():
    """Dispose of the global connection pool (cleanup on shutdown)."""
    await _connection_pool.dispose()
