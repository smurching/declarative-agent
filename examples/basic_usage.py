"""Basic example of using the Declarative Agent SDK."""

import asyncio
from pathlib import Path
import sys

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

from declarative_agent import DeclarativeAgent, AgentRunner


async def main():
    """Run basic agent examples."""
    # Load agent from YAML
    agent_path = Path(__file__).parent / "agents" / "assistant.yaml"
    agent = DeclarativeAgent.from_yaml(agent_path, backend_url="http://localhost:8000")

    print(f"Loaded agent: {agent}")
    print(f"Description: {agent.config.description}\n")

    # Create runner
    user_id = 12345
    async with AgentRunner(agent, user_id) as runner:
        # Example 1: Non-streaming response
        print("=" * 60)
        print("Example 1: Non-streaming response")
        print("=" * 60)

        response = await runner.run(
            message="What is 2+2?",
            stream=False
        )

        print(f"Response ID: {response['id']}")
        print(f"Status: {response['status']}")
        print(f"Output: {response['output'][0]['content']}\n")

        # Example 2: Streaming response
        print("=" * 60)
        print("Example 2: Streaming response")
        print("=" * 60)

        print("User: Tell me a short story about a robot")
        print("Assistant: ", end="", flush=True)

        stream = await runner.run(
            message="Tell me a short story about a robot",
            stream=True
        )

        async for event in stream:
            if event.get("type") == "delta" and "delta" in event:
                delta = event["delta"]
                if "text" in delta:
                    print(delta["text"], end="", flush=True)

        print("\n")

        # Example 3: Background mode
        print("=" * 60)
        print("Example 3: Background mode (for long-running tasks)")
        print("=" * 60)

        response = await runner.run(
            message="Analyze this complex dataset: [large data here]",
            background=True
        )

        print(f"Response ID: {response['id']}")
        print(f"Status: {response['status']}")
        print(f"Task submitted in background. You can retrieve it later using:")
        print(f"  runner.retrieve('{response['id']}')\n")


if __name__ == "__main__":
    print("\nDeclarative Agent SDK - Basic Usage Example")
    print("=" * 60)
    print("\nMake sure the agent backend is running:")
    print("  uvicorn server.main:app --host 0.0.0.0 --port 8000\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        print("\nMake sure the agent backend is running on http://localhost:8000")
