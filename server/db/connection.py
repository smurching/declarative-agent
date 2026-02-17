"""Async database connection pool with support for PostgreSQL and SQLite."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from contextlib import asynccontextmanager
import time
import logging
import os

from server.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """
    Database connection pool with support for PostgreSQL (Lakebase) and SQLite.

    For PostgreSQL: Automatically refreshes OAuth token every 15 minutes.
    For SQLite: Uses a local file-based database (no auth needed).
    """

    def __init__(self):
        self._engine = None
        self._session_maker = None
        self._last_token_refresh = 0
        self._refresh_interval = 900  # 15 minutes in seconds
        self._db_type = None

    async def _get_connection_url(self) -> str:
        """
        Get database engine with appropriate configuration.

        For SQLite: Creates engine once on first call.
        For PostgreSQL: Refreshes OAuth token if more than 15 minutes have elapsed.
        """
        settings = get_settings()
        current_time = time.time()

        # Detect database type
        if self._db_type is None:
            self._db_type = settings.db_type.lower()
            logger.info(f"Initializing database connection pool with type: {self._db_type}")

        # SQLite: Create engine once
        if self._db_type == "sqlite":
            if self._engine is None:
                # Ensure directory exists
                db_path = settings.sqlite_database
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

                connection_url = f"sqlite+aiosqlite:///{db_path}"
                logger.info(f"Creating SQLite database at: {db_path}")

                self._engine = create_async_engine(
                    connection_url,
                    poolclass=StaticPool,  # Use StaticPool for SQLite
                    echo=False,
                    connect_args={"check_same_thread": False},  # Required for async SQLite
                )

                self._session_maker = async_sessionmaker(
                    self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )

        # PostgreSQL: Refresh token periodically
        elif self._db_type == "postgres":
            if current_time - self._last_token_refresh > self._refresh_interval:
                logger.info("Refreshing Databricks OAuth token for database connection")

                # Import here to avoid circular dependency and to allow SQLite without auth
                from server.auth.databricks import get_databricks_oauth_token
                token = await get_databricks_oauth_token()

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
        else:
            raise ValueError(f"Unsupported database type: {self._db_type}")

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
