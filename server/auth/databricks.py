"""Databricks authentication utilities."""
from databricks.sdk import WorkspaceClient
from functools import lru_cache
import os


@lru_cache
def get_workspace_client() -> WorkspaceClient:
    """
    Get WorkspaceClient with OAuth authentication.

    Auto-detects CLI or service principal authentication.
    Returns cached instance for reuse.
    """
    from server.config import get_settings
    settings = get_settings()

    # Use dogfood profile if specified, otherwise default
    profile = os.getenv("DATABRICKS_CLI_PROFILE", "dogfood")

    return WorkspaceClient(
        profile=profile,
        host=settings.databricks_host if settings.databricks_host else None
    )


async def get_databricks_oauth_token() -> str:
    """
    Get OAuth token for database connections.

    Returns:
        Access token string for authenticating to Databricks services.
    """
    w = get_workspace_client()
    return w.config.oauth_token().access_token
