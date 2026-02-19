"""
Backend API contract tests.

Tests that backend /v1/responses implements OpenResponses spec correctly
using the databricks-openai client library.
"""
import pytest
import os
from databricks_openai import DatabricksOpenAI
from databricks.sdk import WorkspaceClient


@pytest.fixture
def backend_client():
    """Create OpenAI client pointing at backend app."""
    backend_url = os.getenv("BACKEND_APP_URL")
    if not backend_url:
        pytest.skip("BACKEND_APP_URL not set")

    w = WorkspaceClient()

    return DatabricksOpenAI(
        base_url=backend_url,
        api_key=w.config.oauth_token().access_token
    )


def test_backend_streaming_contract(backend_client):
    """Verify backend returns proper SSE stream via OpenAI client."""
    response = backend_client.responses.create(
        model="databricks-gpt-5-2",
        input=[{"role": "user", "content": "What is 2+2?"}],
        stream=True,
        databricks_options={"user_id": 123}
    )

    # Collect streaming events
    chunks = []
    for chunk in response:
        chunks.append(chunk)

    assert len(chunks) > 0

    # Validate streaming worked
    full_text = ''.join(
        chunk.output[0].content[0].text
        for chunk in chunks
        if chunk.output and len(chunk.output) > 0
    )
    assert len(full_text) > 0
    assert "4" in full_text


def test_backend_non_streaming_contract(backend_client):
    """Verify backend returns proper Response object."""
    response = backend_client.responses.create(
        model="databricks-gpt-5-2",
        input=[{"role": "user", "content": "Hello"}],
        stream=False,
        databricks_options={"user_id": 123}
    )

    # Validate response structure
    assert response.id is not None
    assert len(response.output) > 0
    assert response.output[0].role == "assistant"
    assert len(response.output[0].content[0].text) > 0


def test_backend_conversation_history(backend_client):
    """Verify backend preserves conversation history."""
    # First message
    resp1 = backend_client.responses.create(
        model="databricks-gpt-5-2",
        input=[{"role": "user", "content": "My name is Alice"}],
        stream=False,
        databricks_options={"user_id": 456}
    )

    # Get conversation ID from response
    conv_id = resp1.conversation_id

    # Follow-up message
    resp2 = backend_client.responses.create(
        model="databricks-gpt-5-2",
        input=[{"role": "user", "content": "What is my name?"}],
        stream=False,
        databricks_options={
            "user_id": 456,
            "conversation_id": conv_id
        }
    )

    response_text = resp2.output[0].content[0].text.lower()
    assert "alice" in response_text


def test_backend_background_mode(backend_client):
    """Verify backend supports background mode."""
    response = backend_client.responses.create(
        model="databricks-gpt-5-2",
        input=[{"role": "user", "content": "Complex task"}],
        background=True,
        databricks_options={"user_id": 789}
    )

    # Background mode returns immediately with ID
    assert response.id is not None
    assert response.status == "in_progress"


def test_backend_requires_valid_model(backend_client):
    """Verify backend validates model parameter."""
    with pytest.raises(Exception):  # Should raise an error for invalid model
        backend_client.responses.create(
            model="invalid-model-name",
            input=[{"role": "user", "content": "Test"}],
            stream=False,
            databricks_options={"user_id": 123}
        )


def test_backend_handles_empty_input(backend_client):
    """Verify backend handles empty input gracefully."""
    with pytest.raises(Exception):  # Should raise an error
        backend_client.responses.create(
            model="databricks-gpt-5-2",
            input=[],
            stream=False,
            databricks_options={"user_id": 123}
        )
