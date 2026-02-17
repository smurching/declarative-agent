"""Admin endpoints for one-time operations like migrations."""
from fastapi import APIRouter, HTTPException
import subprocess
import logging

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin")


@admin_router.post("/migrate")
async def run_migrations():
    """
    Create database schema.

    This should only need to be called once after deployment with a fresh database.
    """
    try:
        logger.info("Creating database schema...")
        from server.db.connection import _connection_pool
        from server.db.models import Base
        from sqlalchemy import text

        # Get a session to access the engine
        session = await _connection_pool.get_session()
        try:
            # Get the engine from the session
            engine = session.get_bind()

            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database schema created successfully")

            # Get list of created tables
            from server.db.models import SCHEMA_NAME
            result = await session.execute(
                text(f"SELECT tablename FROM pg_tables WHERE schemaname = '{SCHEMA_NAME}' ORDER BY tablename")
            )
            tables = [row[0] for row in result.fetchall()]

            return {
                "status": "success",
                "message": "Database schema created successfully",
                "tables_created": tables
            }
        finally:
            await session.close()

    except Exception as e:
        logger.error(f"Schema creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Schema creation failed: {str(e)}"
        )


@admin_router.get("/migrate/status")
async def migration_status():
    """Check current migration status."""
    try:
        from server.db.connection import get_db_context

        async with get_db_context() as session:
            result = await session.execute("SELECT version_num FROM alembic_version")
            version = result.scalar()
            await session.commit()

            if version:
                return {"status": "ok", "current_version": version}
            else:
                return {"status": "no_migrations", "message": "No migrations have been run"}

    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        return {"status": "error", "message": str(e)}
