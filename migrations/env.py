"""Alembic migration environment."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# Import all models to ensure they're registered
from server.db.models import Base
from server.config import get_settings
from server.auth.databricks import get_databricks_oauth_token

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = Base.metadata


def get_url():
    """Get database URL with OAuth token."""
    settings = get_settings()

    # For async operations, we'll use a synchronous token fetch
    import os
    from databricks.sdk import WorkspaceClient

    # Use dogfood profile if specified
    profile = os.getenv("DATABRICKS_CLI_PROFILE", "dogfood")
    w = WorkspaceClient(profile=profile, host=settings.databricks_host if settings.databricks_host else None)
    token = w.config.oauth_token().access_token

    return (
        f"postgresql+asyncpg://{settings.pguser}:{token}@"
        f"{settings.pghost}:{settings.pgport}/{settings.pgdatabase}"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={"ssl": "require"},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection):
    """Execute migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
