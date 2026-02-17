"""Run database migrations."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic import command


def run_migrations():
    """Run all pending database migrations."""
    print("Running database migrations...")

    # Create Alembic config
    alembic_cfg = Config("alembic.ini")

    # Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    print("✓ Migrations completed successfully")


if __name__ == "__main__":
    run_migrations()
