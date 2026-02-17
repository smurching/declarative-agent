"""Configuration management for the agent backend."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import Field, field_validator
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Databricks Configuration
    databricks_host: str = ""
    databricks_token: str = ""

    # Database Configuration
    # Make all database fields optional to allow app to start even if DB not configured
    # DB_TYPE can be "postgres" (for Lakebase) or "sqlite" (for local dev/testing)
    db_type: str = "postgres"
    sqlite_database: str = "./agent_backend.db"  # Path for SQLite database

    # PostgreSQL/Lakebase Configuration
    pghost: str = ""
    pgport: int = 5432
    pgdatabase: str = "databricks_postgres"
    pguser: str = ""

    # LLM Configuration
    databricks_serving_endpoint: str = "databricks-gpt-5-2"

    # App Configuration
    workspace_id: int

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator('pgport', mode='before')
    @classmethod
    def parse_port(cls, v):
        """Parse port from string or int, with fallback."""
        if v is None or v == "":
            return 5432
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                # If port can't be parsed, might be getting wrong env var value
                # Log warning and use default
                print(f"Warning: Could not parse PGPORT value '{v}', using default 5432")
                return 5432
        return 5432


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
