"""Backend server command."""

import click
import subprocess
import sys
import os
from pathlib import Path


@click.command()
@click.option('--port', default=8000, help='Port to run backend on')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def backend_command(port: int, host: str, reload: bool):
    """Start the declarative agent backend server."""
    # Set environment variables
    env = os.environ.copy()
    env['DB_TYPE'] = 'sqlite'

    # Find project root
    project_root = Path(__file__).parent.parent.parent.parent

    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", host,
        "--port", str(port)
    ]

    if reload:
        cmd.append("--reload")

    click.echo(f"Starting backend server on {host}:{port}...")

    # Run uvicorn
    subprocess.run(cmd, env=env, cwd=project_root)
