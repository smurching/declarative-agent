"""
Streaming mode tests for agent app /invocations endpoint.

Tests SSE streaming functionality end-to-end.
"""
import pytest
import os
from databricks.sdk import WorkspaceClient
import httpx
import json


@pytest.fixture
def agent_url():
    """Get agent app URL from environment."""
    url = os.getenv("AGENT_APP_URL")
    if not url:
        pytest.skip("AGENT_APP_URL not set")
    return url


@pytest.fixture
def auth_token():
    """Get authentication token."""
    w = WorkspaceClient()
    return w.config.oauth_token().access_token


@pytest.mark.asyncio
async def test_streaming_basic(agent_url, auth_token):
    """Test basic streaming functionality."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "What is 2+2?"}],
                "stream": True,
                "databricks_options": {"user_id": 123}
            }
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            # Collect SSE events
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass

            # Should have received at least one event
            assert len(events) > 0, "Should receive streaming events"

            # Events should have correct structure
            for event in events:
                assert "type" in event, "Event should have type field"


@pytest.mark.asyncio
async def test_streaming_response_content(agent_url, auth_token):
    """Test that streaming delivers actual content."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "Say hello"}],
                "stream": True,
                "databricks_options": {"user_id": 456}
            }
        ) as response:
            assert response.status_code == 200

            # Collect all text from delta events
            full_text = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        if event.get("type") == "response.output_text.delta":
                            delta = event.get("delta", "")
                            full_text.append(delta)
                    except json.JSONDecodeError:
                        pass

            # Should have received actual content
            text = "".join(full_text)
            assert len(text) > 0, "Should receive text content"
            assert "hello" in text.lower(), "Response should contain 'hello'"


@pytest.mark.asyncio
async def test_streaming_error_handling(agent_url, auth_token):
    """Test streaming handles errors gracefully."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Send invalid request
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [],  # Empty input - should cause error
                "stream": True,
                "databricks_options": {"user_id": 789}
            }
        ) as response:
            # Should return 400 for validation error
            assert response.status_code == 400


@pytest.mark.asyncio
async def test_streaming_conversation_context(agent_url, auth_token):
    """Test streaming works with conversation ID (context preservation)."""
    # First message - non-streaming to get conv_id
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp1 = await client.post(
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "Hello"}],
                "stream": False,
                "databricks_options": {"user_id": 999}
            }
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        conv_id = data1.get("conversation_id")
        assert conv_id is not None, "Should get conversation ID from first message"

        # Second message - streaming with conv_id
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "What is 5+5?"}],
                "stream": True,
                "databricks_options": {
                    "user_id": 999,
                    "conversation_id": conv_id
                }
            }
        ) as response:
            # Main test: streaming should work with conversation_id
            assert response.status_code == 200, "Streaming with conv_id should work"

            # Verify we get valid SSE events
            event_count = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        if "type" in event:
                            event_count += 1
                    except json.JSONDecodeError:
                        pass

            assert event_count > 0, "Should receive streaming events with conversation_id"


@pytest.mark.asyncio
async def test_streaming_vs_non_streaming_consistency(agent_url, auth_token):
    """Test that streaming and non-streaming produce equivalent results."""
    test_message = "What is 3+3?"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Non-streaming request
        resp_non_stream = await client.post(
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": test_message}],
                "stream": False,
                "databricks_options": {"user_id": 1111}
            }
        )
        assert resp_non_stream.status_code == 200
        non_stream_data = resp_non_stream.json()
        non_stream_content = non_stream_data["output"][0]["content"]

        # Streaming request
        full_text = []
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": test_message}],
                "stream": True,
                "databricks_options": {"user_id": 2222}
            }
        ) as response:
            assert response.status_code == 200

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        if event.get("type") == "response.output_text.delta":
                            full_text.append(event.get("delta", ""))
                    except json.JSONDecodeError:
                        pass

        stream_content = "".join(full_text)

        # Both should contain the answer "6"
        assert "6" in non_stream_content, "Non-streaming should contain answer"
        assert "6" in stream_content, "Streaming should contain answer"


@pytest.mark.asyncio
async def test_streaming_authentication_required(agent_url):
    """Test that streaming requires authentication."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={"Content-Type": "application/json"},  # No auth token
            json={
                "input": [{"role": "user", "content": "Test"}],
                "stream": True,
                "databricks_options": {"user_id": 123}
            }
        ) as response:
            # Should require authentication
            assert response.status_code in [401, 302, 307], "Should require authentication"


@pytest.mark.asyncio
async def test_streaming_sse_format(agent_url, auth_token):
    """Test that SSE events follow the correct format."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "Test"}],
                "stream": True,
                "databricks_options": {"user_id": 123}
            }
        ) as response:
            assert response.status_code == 200

            # Check SSE format
            line_count = 0
            async for line in response.aiter_lines():
                line_count += 1

                if line_count > 100:  # Safety limit
                    break

                if line.startswith("data: "):
                    # Valid SSE line
                    assert True
                elif line == "":
                    # Empty lines are okay in SSE
                    assert True
                elif "data: [DONE]" in line:
                    # Done signal
                    break
                else:
                    # Invalid SSE format
                    pytest.fail(f"Invalid SSE line format: {line}")


@pytest.mark.asyncio
async def test_streaming_incremental_delivery(agent_url, auth_token):
    """Test that streaming delivers content incrementally (not all at once)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url}/invocations",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "input": [{"role": "user", "content": "Count from 1 to 10"}],
                "stream": True,
                "databricks_options": {"user_id": 3333}
            }
        ) as response:
            assert response.status_code == 200

            event_count = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        if event.get("type") == "response.output_text.delta":
                            event_count += 1
                    except json.JSONDecodeError:
                        pass

            # Should receive multiple events (incremental delivery)
            assert event_count > 1, f"Should receive multiple events, got {event_count}"
