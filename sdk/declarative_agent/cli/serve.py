"""Serve command - start agent with auto-managed backend."""

import click
import subprocess
import sys
import os
import atexit
import signal
from pathlib import Path
import logging
import threading

from .utils import (
    check_backend_health,
    is_localhost_url,
    start_backend,
    wait_for_backend,
    cleanup_processes,
    stream_process_output
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command()
@click.argument('agent_yaml', type=click.Path(exists=True))
@click.option('--port', default=8001, help='Port to serve agent on')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--backend-url', default='http://localhost:8000', help='Backend API URL')
@click.option('--backend-port', default=8000, help='Backend port if auto-starting')
@click.option('--no-backend', is_flag=True, help="Don't auto-start backend")
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def serve_command(
    agent_yaml: str,
    port: int,
    host: str,
    backend_url: str,
    backend_port: int,
    no_backend: bool,
    reload: bool
):
    """
    Serve a declarative agent from YAML configuration.

    This command:
    1. Checks if backend is running at --backend-url
    2. Auto-starts backend if needed (and URL is localhost)
    3. Starts agent app serving the specified YAML file
    4. Cleans up on exit

    Examples:

        # Serve agent with auto-started backend
        declarative-agent serve my_agent.yaml

        # Serve on custom port
        declarative-agent serve my_agent.yaml --port 8002

        # Use existing backend
        declarative-agent serve my_agent.yaml --backend-url http://backend:8000

        # Don't auto-start backend
        declarative-agent serve my_agent.yaml --no-backend
    """
    agent_path = Path(agent_yaml).resolve()

    if not agent_path.exists():
        click.echo(f"Error: Agent file not found: {agent_path}", err=True)
        sys.exit(1)

    click.echo(f"Loading agent from: {agent_path}")
    click.echo(f"Backend URL: {backend_url}")

    backend_process = None
    agent_process = None

    def cleanup():
        """Cleanup handler."""
        click.echo("\nShutting down...")
        cleanup_processes(agent_process, backend_process)

    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), sys.exit(0)))

    try:
        # Step 1: Check if backend is running (skip for non-localhost with --no-backend)
        if no_backend and not is_localhost_url(backend_url):
            # User explicitly managing backend on remote URL, skip health check
            click.echo(f"Using remote backend at {backend_url} (skipping health check)")
        else:
            backend_healthy = check_backend_health(backend_url)

            if not backend_healthy:
                if no_backend:
                    click.echo(f"Error: Backend not running at {backend_url} and --no-backend specified", err=True)
                    click.echo("Please start the backend manually or remove --no-backend flag", err=True)
                    sys.exit(1)

                if not is_localhost_url(backend_url):
                    click.echo(f"Error: Backend not running at {backend_url}", err=True)
                    click.echo("Cannot auto-start backend for non-localhost URLs", err=True)
                    click.echo("Please start the backend manually or use a localhost URL", err=True)
                    sys.exit(1)

            # Step 2: Auto-start backend
            click.echo(f"Backend not running, starting on port {backend_port}...")
            backend_process = start_backend(port=backend_port, reload=reload)

            # Stream backend logs in background thread
            def stream_backend_logs():
                stream_process_output(backend_process, prefix="[backend] ")

            log_thread = threading.Thread(target=stream_backend_logs, daemon=True)
            log_thread.start()

            # Wait for backend to be healthy
            click.echo("Waiting for backend to start...")
            if not wait_for_backend(backend_url, timeout=30):
                click.echo("Error: Backend failed to start within 30 seconds", err=True)
                if backend_process and backend_process.poll() is not None:
                    click.echo(f"Backend process exited with code: {backend_process.returncode}", err=True)
                cleanup()
                sys.exit(1)

            click.echo("✓ Backend started successfully")
        else:
            click.echo("✓ Backend already running")

        # Step 3: Set environment variables for agent app
        env = os.environ.copy()
        env['AGENT_YAML_PATH'] = str(agent_path)
        env['BACKEND_APP_URL'] = backend_url

        # Find project root
        project_root = Path(__file__).parent.parent.parent.parent

        # Step 4: Start agent app
        cmd = [
            sys.executable, "-m", "uvicorn",
            "agent_app.main:app",
            "--host", host,
            "--port", str(port)
        ]

        if reload:
            cmd.append("--reload")

        click.echo(f"\nStarting agent on {host}:{port}...")
        click.echo(f"Agent endpoint: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/invocations")
        click.echo("\nPress Ctrl+C to stop\n")

        # Run agent app (blocking)
        agent_process = subprocess.Popen(
            cmd,
            env=env,
            cwd=project_root
        )

        # Wait for agent process
        agent_process.wait()

    except KeyboardInterrupt:
        click.echo("\nReceived interrupt signal")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error in serve command")
        sys.exit(1)
    finally:
        cleanup()
