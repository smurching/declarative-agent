"""
Agent app contract tests.

Tests that agent app /invocations proxies correctly to backend
using the databricks-openai client library.
"""
import pytest
import os
from databricks_openai import DatabricksOpenAI
from databricks.sdk import WorkspaceClient
from openai import AuthenticationError


@pytest.fixture
def agent_client():
    """Create OpenAI client pointing at agent app /invocations."""
    agent_url = os.getenv("AGENT_APP_URL")
    if not agent_url:
        pytest.skip("AGENT_APP_URL not set")

    w = WorkspaceClient()

    return DatabricksOpenAI(
        base_url=agent_url,
        api_key=w.config.oauth_token().access_token
    )


def test_agent_app_streaming_contract(agent_client):
    """Verify agent app streams responses correctly."""
    response = agent_client.responses.create(
        model="data_analyst",  # Agent name from YAML
        input=[{"role": "user", "content": "What is 2+2?"}],
        stream=True,
        databricks_options={"user_id": 123}
    )

    # Collect streaming chunks
    chunks = list(response)
    assert len(chunks) > 0

    # Verify we got actual content
    full_text = ''.join(
        chunk.output[0].content[0].text
        for chunk in chunks
        if chunk.output and len(chunk.output) > 0
    )
    assert "4" in full_text


def test_agent_app_non_streaming_contract(agent_client):
    """Verify agent app returns complete responses."""
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Hello"}],
        stream=False,
        databricks_options={"user_id": 123}
    )

    assert response.id is not None
    assert len(response.output) > 0
    assert response.output[0].role == "assistant"


def test_agent_app_requires_auth():
    """Verify agent app requires authentication."""
    agent_url = os.getenv("AGENT_APP_URL")
    if not agent_url:
        pytest.skip("AGENT_APP_URL not set")

    # Create client without valid token
    invalid_client = DatabricksOpenAI(
        base_url=agent_url,
        api_key="invalid-token"
    )

    with pytest.raises(AuthenticationError):
        invalid_client.responses.create(
            model="data_analyst",
            input=[{"role": "user", "content": "Test"}],
            stream=False,
            databricks_options={"user_id": 123}
        )


def test_agent_app_to_backend_permission(agent_client):
    """Verify agent app service principal can call backend."""
    # This validates the CAN_USE permission was granted correctly
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Test"}],
        stream=False,
        databricks_options={"user_id": 123}
    )

    # Should succeed (not 403 Forbidden)
    assert response.id is not None
    assert response.output is not None


def test_agent_app_conversation_history(agent_client):
    """Verify agent app preserves conversation context."""
    # First message
    resp1 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "My favorite number is 42"}],
        stream=False,
        databricks_options={"user_id": 456}
    )

    conv_id = resp1.conversation_id

    # Follow-up
    resp2 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "What is my favorite number?"}],
        stream=False,
        databricks_options={
            "user_id": 456,
            "conversation_id": conv_id
        }
    )

    response_text = resp2.output[0].content[0].text
    assert "42" in response_text


def test_agent_app_handles_invalid_input(agent_client):
    """Verify agent app validates input."""
    with pytest.raises(Exception):  # Should raise validation error
        agent_client.responses.create(
            model="data_analyst",
            input=[],  # Empty input
            stream=False,
            databricks_options={"user_id": 123}
        )


def test_agent_app_background_mode(agent_client):
    """Verify agent app supports background mode."""
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Complex task"}],
        background=True,
        databricks_options={"user_id": 789}
    )

    # Background mode returns immediately with ID
    assert response.id is not None
    assert response.status == "in_progress"
