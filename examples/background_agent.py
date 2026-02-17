"""Example of using an agent with background mode for long-running tasks."""

import asyncio
from pathlib import Path
import sys

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

from declarative_agent import DeclarativeAgent, AgentRunner


async def main():
    """Demonstrate background execution with the data analyst agent."""
    # Load data analyst agent
    agent_path = Path(__file__).parent / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(agent_path, backend_url="http://localhost:8000")

    print(f"Loaded agent: {agent.config.name}")
    print(f"Description: {agent.config.description}")
    print(f"Supports background: {agent.config.supports_background}\n")

    user_id = 12345
    async with AgentRunner(agent, user_id) as runner:
        # Submit a long-running analysis task in background
        print("=" * 60)
        print("Submitting long-running analysis task in background...")
        print("=" * 60)

        task_description = """
        Analyze the following business metrics:
        - Revenue: $1.2M (up 15% YoY)
        - Customer count: 5,000 (up 25% YoY)
        - Churn rate: 3% (down from 5%)
        - Average customer value: $240

        Please provide:
        1. Key insights from the data
        2. Trends and patterns
        3. Recommendations for improving metrics
        """

        response = await runner.run(
            message=task_description,
            background=True  # Run in background
        )

        response_id = response['id']
        print(f"\n✓ Task submitted successfully!")
        print(f"  Response ID: {response_id}")
        print(f"  Status: {response['status']}")
        print(f"  Conversation ID: {response.get('conversation_id')}")

        # Simulate waiting for the task to complete
        print("\nWaiting for task to complete...")
        print("(In a real application, you could check status periodically)\n")

        # Wait a bit, then retrieve the result
        await asyncio.sleep(3)

        # Retrieve the completed response
        print("=" * 60)
        print("Retrieving completed analysis...")
        print("=" * 60)

        result = await runner.retrieve(response_id)

        print(f"\nStatus: {result['status']}")
        if result['output']:
            print(f"\nAnalysis Results:")
            print("-" * 60)
            for item in result['output']:
                print(item['content'])
        else:
            print("\nTask is still in progress. Check again later.")

        # Example: Continue the conversation
        if response.get('conversation_id'):
            print("\n" + "=" * 60)
            print("Continuing the conversation...")
            print("=" * 60)

            followup = await runner.run(
                message="Can you elaborate on recommendation #1?",
                stream=False,
                conversation_id=response['conversation_id']
            )

            print(f"\nFollow-up response:")
            print("-" * 60)
            print(followup['output'][0]['content'])


if __name__ == "__main__":
    print("\nDeclarative Agent SDK - Background Mode Example")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("  1. Submitting a long-running task in background mode")
    print("  2. Retrieving the completed result")
    print("  3. Continuing the conversation with follow-up questions")
    print("\nMake sure the agent backend is running:")
    print("  uvicorn server.main:app --host 0.0.0.0 --port 8000\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        print("\nMake sure the agent backend is running on http://localhost:8000")
