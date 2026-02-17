"""Pytest configuration and fixtures for agent backend tests."""
import pytest
import asyncio
from typing import AsyncGenerator, Generator, Optional, Dict, Union
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import os
from uuid import uuid4
import httpx

from openai import AsyncOpenAI
from databricks_openai import AsyncDatabricksOpenAI

from server.db.models import Base
from server.db.connection import _connection_pool
from server.config import get_settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """
    Create a test database engine.

    Uses SQLite for local testing (no auth needed).
    Uses PostgreSQL for deployed testing (with auth).
    """
    settings = get_settings()

    # Use SQLite for local testing by default
    db_type = os.getenv("DB_TYPE", "sqlite").lower()

    if db_type == "sqlite":
        # SQLite: Create temporary test database
        test_db_path = "./test_agent_backend.db"

        # Remove existing test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        test_db_url = f"sqlite+aiosqlite:///{test_db_path}"

        from sqlalchemy.pool import StaticPool
        engine = create_async_engine(
            test_db_url,
            poolclass=StaticPool,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL: For deployed testing (requires auth)
        from server.auth.databricks import get_databricks_oauth_token
        token = await get_databricks_oauth_token()

        test_db_url = (
            f"postgresql+asyncpg://{settings.pguser}:{token}@"
            f"{settings.pghost}:{settings.pgport}/test_{settings.pgdatabase}"
        )

        engine = create_async_engine(
            test_db_url,
            poolclass=NullPool,
            echo=False,
        )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup: drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    # Remove SQLite test database
    if db_type == "sqlite" and os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def base_url() -> str:
    """
    Get the base URL for the API.

    Defaults to local server, but can be overridden via BASE_URL env var
    for testing deployed apps.
    """
    return os.getenv("BASE_URL", "http://localhost:8000")


@pytest.fixture
def is_local(base_url: str) -> bool:
    """Check if we're testing against local server (no auth needed)."""
    return "localhost" in base_url or "127.0.0.1" in base_url


@pytest.fixture
async def openai_client(base_url: str, is_local: bool) -> AsyncGenerator[Union[AsyncOpenAI, AsyncDatabricksOpenAI], None]:
    """
    Provide the appropriate OpenAI client based on environment.

    - Local testing: Uses AsyncOpenAI with custom base_url and empty API key
    - Databricks Apps: Uses AsyncDatabricksOpenAI with automatic auth

    The client can be used for:
    1. OpenAI-compatible endpoints via high-level API (where available)
    2. Custom endpoints via client.post(), client.get(), etc.

    Environment variables:
    - BASE_URL: Set to deployed app URL to test Databricks Apps (default: http://localhost:8000)

    Examples:
        # Test locally (no auth)
        pytest

        # Test deployed app (with Databricks auth)
        BASE_URL=https://your-workspace.cloud.databricks.com/apps/your-app pytest
    """
    # Ensure base_url ends with /v1 for OpenAI client
    if not base_url.endswith("/v1"):
        openai_base_url = f"{base_url}/v1"
    else:
        openai_base_url = base_url

    if is_local:
        # Local testing - use standard OpenAI client with dummy key
        client = AsyncOpenAI(
            base_url=openai_base_url,
            api_key="not-needed",  # Dummy key for local testing
        )
    else:
        # Databricks Apps - use DatabricksOpenAI with automatic auth
        # Use the profile from environment variable if set
        profile = os.getenv("DATABRICKS_CLI_PROFILE")
        if profile:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient(profile=profile)
            client = AsyncDatabricksOpenAI(
                base_url=openai_base_url,
                workspace_client=w,
            )
        else:
            client = AsyncDatabricksOpenAI(
                base_url=openai_base_url,
            )

    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
async def async_client(base_url: str, is_local: bool) -> httpx.AsyncClient:
    """
    Provide an authenticated httpx client for custom API endpoints.

    Use this for all custom endpoints since they're not part of the official OpenAI API.
    This maintains proper authentication (local: no auth, deployed: OAuth) while
    allowing us to call our custom endpoints.
    """
    if is_local:
        # Local testing - no auth needed
        client = httpx.AsyncClient(base_url=base_url)
    else:
        # Databricks Apps - use OAuth token
        profile = os.getenv("DATABRICKS_CLI_PROFILE")
        if profile:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient(profile=profile)
            token = w.config.oauth_token().access_token
            client = httpx.AsyncClient(
                base_url=base_url,
                headers={"Authorization": f"Bearer {token}"}
            )
        else:
            # Fallback to no auth
            client = httpx.AsyncClient(base_url=base_url)

    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def sample_user_id() -> int:
    """Provide a sample user ID for tests."""
    return 12345


@pytest.fixture
def sample_workspace_id() -> int:
    """Provide a sample workspace ID for tests."""
    settings = get_settings()
    return settings.workspace_id


@pytest.fixture
def sample_conversation_payload(sample_user_id):
    """Provide a sample conversation request payload."""
    return {
        "input": [{"role": "user", "content": "Hello, this is a test message"}],
        "stream": False,
        "databricks_options": {"user_id": sample_user_id}
    }


@pytest.fixture
def sample_streaming_payload(sample_user_id):
    """Provide a sample streaming request payload."""
    return {
        "input": [{"role": "user", "content": "Count to 3"}],
        "stream": True,
        "databricks_options": {"user_id": sample_user_id}
    }


@pytest.fixture
def sample_background_payload(sample_user_id):
    """Provide a sample background mode request payload."""
    return {
        "input": [{"role": "user", "content": "Long running task"}],
        "background": True,
        "databricks_options": {"user_id": sample_user_id}
    }


@pytest.fixture
async def existing_conversation(db_session, sample_user_id, sample_workspace_id):
    """
    Create an existing conversation with messages for testing.

    Returns the conversation object with pre-populated messages.
    """
    from server.db.queries import create_conversation, save_message
    from server.db.models import MessageRole

    # Create conversation
    conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
    await db_session.commit()

    # Add some messages
    await save_message(
        db_session,
        conv.id,
        MessageRole.USER,
        {"text": "First user message"},
        0
    )
    await save_message(
        db_session,
        conv.id,
        MessageRole.ASSISTANT,
        {"text": "First assistant response"},
        1
    )
    await save_message(
        db_session,
        conv.id,
        MessageRole.USER,
        {"text": "Second user message"},
        2
    )
    await db_session.commit()

    return conv


@pytest.fixture(autouse=True)
async def cleanup_connection_pool():
    """Cleanup connection pool after each test."""
    yield
    # Reset connection pool state if needed
    pass
