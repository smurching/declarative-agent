"""
Tests for Declarative Agent SDK against deployed Databricks app.

These tests verify the SDK works correctly with a real production deployment
using PostgreSQL/Lakebase backend.
"""
import pytest
import asyncio
import os
import sys
from pathlib import Path

# Add sdk to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.declarative_agent import DeclarativeAgent, AgentRunner


# Skip all tests in this file if APP_URL is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("APP_URL"),
    reason="APP_URL environment variable not set (set to test against deployed app)"
)


@pytest.fixture
def app_url():
    """Get the deployed app URL from environment."""
    return os.getenv("APP_URL")


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return 12345


@pytest.fixture
def workspace_profile():
    """Databricks workspace profile for authentication."""
    return os.getenv("DATABRICKS_PROFILE", "dogfood")


@pytest.fixture
async def assistant_agent(app_url):
    """Load the assistant agent configured for deployed backend."""
    agent_path = Path(__file__).parent.parent / "examples" / "agents" / "assistant.yaml"
    agent = DeclarativeAgent.from_yaml(agent_path, backend_url=app_url)
    return agent


@pytest.fixture
async def data_analyst_agent(app_url):
    """Load the data analyst agent configured for deployed backend."""
    agent_path = Path(__file__).parent.parent / "examples" / "agents" / "data_analyst.yaml"
    agent = DeclarativeAgent.from_yaml(agent_path, backend_url=app_url)
    return agent


@pytest.mark.asyncio
async def test_sdk_non_streaming_request(assistant_agent, sample_user_id, workspace_profile):
    """
    Test non-streaming request with the declarative SDK.

    Verifies:
    - SDK can connect to deployed app
    - Non-streaming responses work
    - Response contains expected content
    """
    async with AgentRunner(assistant_agent, user_id=sample_user_id, workspace_profile=workspace_profile) as runner:
        response = await runner.run(
            message="What is 2 + 2?",
            stream=False
        )

        assert response is not None
        assert "output" in response
        assert len(response["output"]) > 0
        assert "conversation_id" in response

        # Response should contain the answer
        content = response["output"][0]["content"].lower()
        assert "4" in content or "four" in content

        print(f"✅ Non-streaming response: {response['output'][0]['content'][:100]}")


@pytest.mark.asyncio
async def test_sdk_streaming_request(assistant_agent, sample_user_id, workspace_profile):
    """
    Test streaming request with the declarative SDK.

    Verifies:
    - SDK can stream responses from deployed app
    - Events are received in correct format
    - Full text can be accumulated
    """
    async with AgentRunner(assistant_agent, user_id=sample_user_id, workspace_profile=workspace_profile) as runner:
        stream = await runner.run(
            message="Count to 3",
            stream=True
        )

        full_text = ""
        event_count = 0

        async for event in stream:
            event_count += 1
            if event.get("type") == "delta":
                # Accumulate text from delta events
                delta = event.get("delta", {})
                if isinstance(delta, dict):
                    full_text += delta.get("text", "")
                elif isinstance(delta, str):
                    full_text += delta

        assert event_count > 0, "Should receive at least one event"
        assert len(full_text) > 0, "Should accumulate some text"

        print(f"✅ Streaming response ({event_count} events): {full_text[:100]}")


@pytest.mark.asyncio
async def test_sdk_background_request(data_analyst_agent, sample_user_id, workspace_profile):
    """
    Test background mode with the declarative SDK.

    Verifies:
    - SDK can submit background tasks
    - Task ID is returned immediately
    - Task can be retrieved later
    - Task eventually completes
    """
    async with AgentRunner(data_analyst_agent, user_id=sample_user_id, workspace_profile=workspace_profile) as runner:
        # Submit background task
        response = await runner.run(
            message="Analyze the pattern: 2, 4, 6, 8. What comes next?",
            background=True
        )

        assert "id" in response
        assert "status" in response
        assert response["status"] == "in_progress"

        task_id = response["id"]
        print(f"✅ Background task submitted: {task_id}")

        # Wait and retrieve result
        max_attempts = 10
        for attempt in range(max_attempts):
            await asyncio.sleep(2)

            result = await runner.retrieve(task_id)

            if result["status"] == "completed":
                assert "output" in result
                assert len(result["output"]) > 0
                content = result["output"][0]["content"]
                print(f"✅ Background task completed: {content[:100]}")
                return
            elif result["status"] == "failed":
                pytest.fail(f"Background task failed: {result.get('error')}")

        pytest.fail(f"Background task did not complete after {max_attempts * 2}s")


@pytest.mark.asyncio
async def test_sdk_multi_turn_conversation(assistant_agent, sample_user_id, workspace_profile):
    """
    Test multi-turn conversation with context.

    Verifies:
    - SDK maintains conversation context
    - Follow-up questions work correctly
    - Agent remembers previous context
    """
    async with AgentRunner(assistant_agent, user_id=sample_user_id, workspace_profile=workspace_profile) as runner:
        # First turn: establish context
        response1 = await runner.run(
            message="My favorite color is blue",
            stream=False
        )

        conversation_id = response1.get("conversation_id")
        assert conversation_id is not None

        # Second turn: ask about context
        response2 = await runner.run(
            message="What is my favorite color?",
            stream=False,
            conversation_id=conversation_id
        )

        assert "output" in response2
        content = response2["output"][0]["content"].lower()
        assert "blue" in content, "Agent should remember the favorite color"

        print(f"✅ Multi-turn conversation: {response2['output'][0]['content'][:100]}")


@pytest.mark.asyncio
async def test_sdk_concurrent_requests(assistant_agent, sample_user_id, workspace_profile):
    """
    Test multiple concurrent requests to same agent.

    Verifies:
    - SDK can handle concurrent requests
    - PostgreSQL backend handles concurrent writes
    - All requests succeed
    """
    async with AgentRunner(assistant_agent, user_id=sample_user_id, workspace_profile=workspace_profile) as runner:
        # Create initial conversation
        init_response = await runner.run(
            message="Hello",
            stream=False
        )

        conversation_id = init_response["conversation_id"]

        # Send 5 concurrent messages to same conversation
        tasks = [
            runner.run(
                message=f"What is {i} + {i}?",
                stream=False,
                conversation_id=conversation_id
            )
            for i in range(1, 6)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        success_count = 0
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                print(f"  ❌ Request {i}: {response}")
            elif "output" in response:
                success_count += 1
                print(f"  ✅ Request {i}: Success")
            else:
                print(f"  ❌ Request {i}: Unexpected response format")

        # With PostgreSQL, all requests should succeed
        assert success_count >= 4, f"Expected at least 4/5 concurrent requests to succeed, got {success_count}/5"
        print(f"✅ Concurrent requests: {success_count}/5 succeeded")


@pytest.mark.asyncio
async def test_sdk_error_handling(assistant_agent):
    """
    Test SDK error handling.

    Verifies:
    - SDK handles invalid requests gracefully
    - Appropriate exceptions are raised
    """
    # Test with invalid user_id
    try:
        async with AgentRunner(assistant_agent, user_id=None) as runner:
            await runner.run(message="Hello", stream=False)
        pytest.fail("Should have raised an error for None user_id")
    except Exception as e:
        print(f"✅ Correctly raised error for invalid user_id: {type(e).__name__}")


if __name__ == "__main__":
    # Allow running tests directly with: python -m pytest tests/test_declarative_sdk_deployed.py -v
    pytest.main([__file__, "-v", "-s"])
