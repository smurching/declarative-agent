"""CLI entry point for declarative-agent."""

import click
from .serve import serve_command
from .backend import backend_command


@click.group()
@click.version_option(version="0.1.0", prog_name="declarative-agent")
def cli():
    """
    Declarative Agent CLI - Build and deploy AI agents with YAML.

    Define your agent in a YAML file and serve it with a single command.
    No Python code required!

    Examples:

        # Serve an agent (auto-starts backend)
        declarative-agent serve my_agent.yaml

        # Start just the backend
        declarative-agent backend

    Get started at: https://github.com/smurching/declarative-agent
    """
    pass


# Register commands
cli.add_command(serve_command, name="serve")
cli.add_command(backend_command, name="backend")


if __name__ == "__main__":
    cli()
