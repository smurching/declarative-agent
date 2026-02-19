"""
Example: Using the Data Analyst Agent with streaming, background mode, and tool calling.

This demonstrates all three key features of the OpenResponses API:
1. Streaming - Real-time responses for interactive queries
2. Background mode - Async execution for long-running analysis
3. Tool calling - Agent uses SQL, Python, and vector search tools
"""
import asyncio
from pathlib import Path
from sdk.declarative_agent import DeclarativeAgent, AgentRunner


async def streaming_example():
    """Example 1: Streaming mode for quick interactive queries."""
    print("=" * 60)
    print("STREAMING MODE: Quick exploratory query")
    print("=" * 60)

    # Load agent
    agent_path = Path(__file__).parent / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(
        agent_path,
        backend_url="http://localhost:8000"  # or your deployed app URL
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Stream a quick query
        stream = await runner.run(
            message="What were our total sales last month?",
            stream=True
        )

        print("\nAgent response (streaming):")
        async for event in stream:
            if event.get("type") == "delta":
                # Print text as it arrives
                delta = event.get("delta", {})
                text = delta.get("text", "") if isinstance(delta, dict) else delta
                print(text, end="", flush=True)
        print("\n")


async def background_example():
    """Example 2: Background mode for long-running analysis."""
    print("=" * 60)
    print("BACKGROUND MODE: Complex multi-step analysis")
    print("=" * 60)

    # Load agent
    agent_path = Path(__file__).parent / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(
        agent_path,
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Submit background task for complex analysis
        response = await runner.run(
            message="""
            Generate a comprehensive quarterly report for Q4 2024:
            1. Total revenue by region with YoY growth
            2. Top 10 customers by lifetime value
            3. Product category performance trends
            4. Create visualizations for each metric
            5. Identify top 3 insights and recommendations
            """,
            background=True
        )

        task_id = response["id"]
        print(f"✓ Background task submitted: {task_id}")
        print(f"  Status: {response['status']}")
        print("\nPolling for completion...")

        # Poll for completion
        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(2)

            result = await runner.retrieve(task_id)
            status = result["status"]

            print(f"  [{attempt+1}/{max_attempts}] Status: {status}")

            if status == "completed":
                print("\n✓ Analysis completed!")
                print("\nResults:")
                print(result["output"][0]["content"][:500] + "...")
                return
            elif status == "failed":
                print(f"\n✗ Analysis failed: {result.get('error')}")
                return

        print(f"\n⚠ Analysis still in progress after {max_attempts * 2}s")


async def tool_calling_example():
    """Example 3: Tool calling - Agent uses SQL, Python, vector search."""
    print("=" * 60)
    print("TOOL CALLING: Multi-tool analysis workflow")
    print("=" * 60)

    # Load agent
    agent_path = Path(__file__).parent / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(
        agent_path,
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Ask a question that requires multiple tools
        response = await runner.run(
            message="""
            Compare our sales performance to industry benchmarks:
            1. Query our Q4 revenue by product category
            2. Use vector search to find similar benchmark reports
            3. Create a Python visualization comparing our performance
            """,
            stream=False
        )

        print("\nAgent used multiple tools:")
        print("  1. SQL query on sales_data table")
        print("  2. Vector search on analysis_history_index")
        print("  3. Python code_interpreter for visualization")
        print("\nFinal result:")
        print(response["output"][0]["content"][:500] + "...")


async def multi_turn_example():
    """Example 4: Multi-turn conversation with context."""
    print("=" * 60)
    print("MULTI-TURN: Conversation with context")
    print("=" * 60)

    # Load agent
    agent_path = Path(__file__).parent / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(
        agent_path,
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Turn 1: Initial analysis
        response1 = await runner.run(
            message="What's our average deal size by region?",
            stream=False
        )
        conversation_id = response1["conversation_id"]
        print(f"\nTurn 1: {response1['output'][0]['content'][:200]}...\n")

        # Turn 2: Follow-up (agent remembers context)
        response2 = await runner.run(
            message="How has that changed over the past year?",
            stream=False,
            conversation_id=conversation_id
        )
        print(f"Turn 2: {response2['output'][0]['content'][:200]}...\n")

        # Turn 3: Drill down
        response3 = await runner.run(
            message="Show me the top 5 deals in the highest performing region",
            stream=False,
            conversation_id=conversation_id
        )
        print(f"Turn 3: {response3['output'][0]['content'][:200]}...\n")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("DATA ANALYST AGENT EXAMPLES")
    print("Demonstrates: Streaming, Background Mode, Tool Calling")
    print("=" * 60 + "\n")

    # Run examples sequentially
    await streaming_example()
    await asyncio.sleep(1)

    await background_example()
    await asyncio.sleep(1)

    await tool_calling_example()
    await asyncio.sleep(1)

    await multi_turn_example()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
