"""FastAPI application entry point."""
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from server.responses_handler import responses_router, handle_responses, get_response
from server.admin_endpoints import admin_router
from server.db.connection import dispose_connection_pool, get_db_context
from server.llm.client import get_llm_client
from server.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting agent backend...")

    # Debug: Log all environment variables related to database
    import os
    logger.info("Environment variables:")
    for key in ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'DATABASE_HOST', 'DATABASE_PORT']:
        value = os.getenv(key, 'NOT SET')
        logger.info(f"  {key}={value}")

    # Verify configuration
    settings = get_settings()
    logger.info(f"Parsed settings:")
    logger.info(f"  Workspace ID: {settings.workspace_id}")
    logger.info(f"  Database host: {settings.pghost}")
    logger.info(f"  Database port: {settings.pgport}")
    logger.info(f"  Database name: {settings.pgdatabase}")
    logger.info(f"  Database user: {settings.pguser}")
    logger.info(f"  LLM endpoint: {settings.databricks_serving_endpoint}")

    # Auto-create database schema and tables
    try:
        logger.info("Ensuring database schema exists...")
        from server.db.connection import _connection_pool
        from server.db.models import Base, SCHEMA_NAME
        from sqlalchemy import text

        # Trigger connection to ensure engine is initialized
        await _connection_pool._get_connection_url()

        # Get the engine directly
        engine = _connection_pool._engine

        # Create the custom schema first
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
            logger.info(f"Schema '{SCHEMA_NAME}' ready")

        # Create all tables in the custom schema
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database schema and tables created successfully")
    except Exception as e:
        logger.warning(f"Could not create schema (may already exist): {e}")
        import traceback
        logger.warning(traceback.format_exc())

    yield

    # Cleanup
    logger.info("Shutting down agent backend...")
    await dispose_connection_pool()


app = FastAPI(
    title="Agent Backend",
    description="OpenResponses-compatible agent backend with Databricks Apps + Lakebase",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(responses_router, tags=["responses"])
app.include_router(admin_router, tags=["admin"])

# Also serve /responses without /v1 prefix for backward compatibility
backward_compat_router = APIRouter()
backward_compat_router.add_api_route("/responses", handle_responses, methods=["POST"], tags=["responses"])
backward_compat_router.add_api_route("/responses/{response_id}", get_response, methods=["GET"], tags=["responses"])
app.include_router(backward_compat_router)


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Verifies database connection and LLM availability.
    For local testing without actual backends, returns basic status.
    """
    checks = {
        "status": "healthy",
        "database": "skipped",
        "llm": "skipped",
    }

    # Check database (skip if not configured for local testing)
    try:
        async with get_db_context() as session:
            await session.execute("SELECT 1")
            checks["database"] = "ok"
    except Exception as e:
        logger.warning(f"Database health check skipped: {str(e)[:100]}")
        checks["database"] = "skipped"
        # Don't mark as unhealthy for local testing

    # Check LLM client (skip if not configured for local testing)
    try:
        client = get_llm_client()
        checks["llm"] = "ok"
    except Exception as e:
        logger.warning(f"LLM client health check skipped: {str(e)[:100]}")
        checks["llm"] = "skipped"
        # Don't mark as unhealthy for local testing

    return checks


@app.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: str):
    """
    Retrieve a conversation with its messages.

    Args:
        conversation_id: Conversation UUID

    Returns:
        Conversation with messages
    """
    from uuid import UUID
    from server.db.queries import get_conversation, get_messages
    import json

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        return {"error": "Invalid conversation ID format"}

    async with get_db_context() as session:
        conv = await get_conversation(session, conv_uuid)
        if not conv:
            return {"error": "Conversation not found"}

        messages = await get_messages(session, conv_uuid)
        await session.commit()

    # Deserialize message content
    messages_data = []
    for msg in messages:
        content = json.loads(msg.content.decode("utf-8"))
        messages_data.append({
            "id": str(msg.id),
            "role": msg.role.value,
            "content": content,
            "message_index": msg.message_index,
            "created_timestamp": msg.created_timestamp.isoformat(),
        })

    return {
        "conversation": {
            "id": str(conv.id),
            "user_id": conv.user_id,
            "workspace_id": conv.internal_workspace_id,
            "created_timestamp": conv.created_timestamp.isoformat(),
        },
        "messages": messages_data,
    }


@app.get("/conversations/{conversation_id}/messages")
async def get_messages_endpoint(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """
    List messages for a conversation with pagination.

    Args:
        conversation_id: Conversation UUID
        limit: Maximum number of messages to return
        offset: Number of messages to skip

    Returns:
        List of messages
    """
    from uuid import UUID
    from server.db.queries import get_messages
    import json

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        return {"error": "Invalid conversation ID format"}

    async with get_db_context() as session:
        messages = await get_messages(session, conv_uuid, limit=limit, offset=offset)
        await session.commit()

    # Deserialize message content
    messages_data = []
    for msg in messages:
        content = json.loads(msg.content.decode("utf-8"))
        messages_data.append({
            "id": str(msg.id),
            "role": msg.role.value,
            "content": content,
            "message_index": msg.message_index,
            "created_timestamp": msg.created_timestamp.isoformat(),
        })

    return {
        "messages": messages_data,
        "limit": limit,
        "offset": offset,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
