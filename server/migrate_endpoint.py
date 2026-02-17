"""Migration endpoint for running database migrations from deployed app."""
from fastapi import APIRouter, HTTPException
from alembic.config import Config
from alembic import command
import logging

logger = logging.getLogger(__name__)

migrate_router = APIRouter()


@migrate_router.post("/admin/migrate")
async def run_migrations():
    """
    Run database migrations.

    This endpoint allows running migrations from the deployed app,
    which has proper service principal credentials.
    """
    try:
        logger.info("Running database migrations...")

        # Configure Alembic
        alembic_cfg = Config("alembic.ini")

        # Run migrations
        command.upgrade(alembic_cfg, "head")

        logger.info("Migrations completed successfully")
        return {"status": "success", "message": "Migrations completed successfully"}

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@migrate_router.get("/admin/migrate/status")
async def migration_status():
    """Check current migration status."""
    try:
        from server.db.connection import get_db_context

        async with get_db_context() as session:
            # Try to query alembic_version table
            result = await session.execute("SELECT version_num FROM alembic_version")
            version = result.scalar()

            if version:
                return {"status": "ok", "current_version": version}
            else:
                return {"status": "no_migrations", "message": "No migrations have been run"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
