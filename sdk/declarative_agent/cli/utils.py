"""Utility functions for CLI."""

import httpx
import subprocess
import sys
import os
import time
import signal
import psutil
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def check_backend_health(backend_url: str, timeout: float = 2.0) -> bool:
    """
    Check if backend is healthy.

    Args:
        backend_url: Backend URL to check
        timeout: Timeout in seconds

    Returns:
        True if backend is healthy, False otherwise
    """
    try:
        response = httpx.get(f"{backend_url}/health", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def is_localhost_url(url: str) -> bool:
    """Check if URL points to localhost."""
    return "localhost" in url or "127.0.0.1" in url


def find_backend_process(port: int) -> Optional[int]:
    """
    Find backend process running on given port.

    Args:
        port: Port number to check

    Returns:
        PID of process or None if not found
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if cmdline and 'uvicorn' in ' '.join(cmdline) and 'server.main:app' in ' '.join(cmdline):
                    # Check if process is listening on the port
                    connections = proc.connections()
                    for conn in connections:
                        if conn.laddr.port == port:
                            return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.debug(f"Error finding backend process: {e}")
    return None


def start_backend(port: int = 8000, reload: bool = False) -> subprocess.Popen:
    """
    Start backend server in subprocess.

    Args:
        port: Port to run backend on
        reload: Enable auto-reload

    Returns:
        Subprocess handle
    """
    env = os.environ.copy()
    env['DB_TYPE'] = 'sqlite'

    # Find project root (where server/ directory is)
    project_root = Path(__file__).parent.parent.parent.parent

    cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", "0.0.0.0",
        "--port", str(port)
    ]

    if reload:
        cmd.append("--reload")

    logger.info(f"Starting backend on port {port}...")
    logger.debug(f"Command: {' '.join(cmd)}")
    logger.debug(f"Working directory: {project_root}")

    process = subprocess.Popen(
        cmd,
        env=env,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    return process


def wait_for_backend(backend_url: str, timeout: int = 30, check_interval: float = 0.5) -> bool:
    """
    Wait for backend to become healthy.

    Args:
        backend_url: Backend URL to check
        timeout: Maximum time to wait in seconds
        check_interval: Time between checks in seconds

    Returns:
        True if backend became healthy, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if check_backend_health(backend_url):
            return True
        time.sleep(check_interval)

    return False


def stop_process(process: subprocess.Popen, timeout: int = 5):
    """
    Stop a subprocess gracefully.

    Args:
        process: Subprocess to stop
        timeout: Timeout for graceful shutdown
    """
    if process.poll() is None:
        # Try graceful shutdown
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Force kill if still running
            process.kill()
            process.wait()


def cleanup_processes(*processes: subprocess.Popen):
    """Clean up multiple processes on exit."""
    for process in processes:
        if process:
            try:
                stop_process(process)
            except Exception as e:
                logger.debug(f"Error stopping process: {e}")


def stream_process_output(process: subprocess.Popen, prefix: str = ""):
    """
    Stream process output to logger.

    Args:
        process: Process to stream from
        prefix: Prefix for log lines
    """
    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            logger.info(f"{prefix}{line.rstrip()}")
