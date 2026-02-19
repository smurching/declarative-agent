"""
End-to-end integration tests.

Tests the full flow: User → Agent App → Backend → LLM
using the databricks-openai client library.
"""
import pytest
import os
from databricks_openai import DatabricksOpenAI
from databricks.sdk import WorkspaceClient


@pytest.fixture
def agent_client():
    """OpenAI client for agent app e2e tests."""
    agent_url = os.getenv("AGENT_APP_URL")
    if not agent_url:
        pytest.skip("AGENT_APP_URL not set")

    w = WorkspaceClient()

    return DatabricksOpenAI(
        base_url=agent_url,
        api_key=w.config.oauth_token().access_token
    )


def test_e2e_data_analyst_query(agent_client):
    """Test complete flow with data analyst agent."""
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "What is 2+2?"}],
        stream=False,
        databricks_options={"user_id": 123}
    )

    # Verify response structure
    assert response.id is not None
    assert len(response.output) > 0
    assert response.output[0].role == "assistant"

    # Verify LLM actually responded
    content = response.output[0].content[0].text.lower()
    assert "4" in content  # 2+2=4


def test_e2e_multi_turn_conversation(agent_client):
    """Test multi-turn conversation preserves context."""
    # Turn 1
    resp1 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "I like the color red"}],
        stream=False,
        databricks_options={"user_id": 456}
    )

    conv_id = resp1.conversation_id

    # Turn 2 - should remember
    resp2 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "What color do I like?"}],
        stream=False,
        databricks_options={
            "user_id": 456,
            "conversation_id": conv_id
        }
    )

    content = resp2.output[0].content[0].text.lower()
    assert "red" in content


def test_e2e_streaming_flow(agent_client):
    """Test streaming works end-to-end."""
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Count to 3"}],
        stream=True,
        databricks_options={"user_id": 789}
    )

    # Collect stream
    chunks = list(response)
    assert len(chunks) > 0

    # Verify streaming produced content
    full_text = ''.join(
        chunk.output[0].content[0].text
        for chunk in chunks
        if chunk.output and len(chunk.output) > 0
    )
    assert len(full_text) > 0


def test_e2e_different_users_isolated(agent_client):
    """Test that different users have isolated conversations."""
    # User 1 conversation
    resp1 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "My secret is X"}],
        stream=False,
        databricks_options={"user_id": 100}
    )

    # User 2 conversation - should not see User 1's secret
    resp2 = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "What is the secret?"}],
        stream=False,
        databricks_options={"user_id": 200}
    )

    content = resp2.output[0].content[0].text.lower()
    # User 2 should not know about User 1's secret
    assert "x" not in content or "don't" in content or "not" in content


def test_e2e_agent_instructions_applied(agent_client):
    """Test that agent instructions from YAML are applied."""
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Who are you?"}],
        stream=False,
        databricks_options={"user_id": 999}
    )

    content = response.output[0].content[0].text.lower()

    # Data analyst agent should identify itself appropriately
    # Check for keywords that indicate it's a data analyst
    assert any(keyword in content for keyword in [
        "analyst", "data", "analysis", "sql", "python", "help"
    ])


def test_e2e_error_handling(agent_client):
    """Test error handling in the full stack."""
    # Send a request that might cause issues
    with pytest.raises(Exception):
        agent_client.responses.create(
            model="data_analyst",
            input=[],  # Empty input should cause error
            stream=False,
            databricks_options={"user_id": 123}
        )


def test_e2e_background_task_retrieval(agent_client):
    """Test background task creation and retrieval."""
    # Start background task
    response = agent_client.responses.create(
        model="data_analyst",
        input=[{"role": "user", "content": "Tell me a story"}],
        background=True,
        databricks_options={"user_id": 888}
    )

    assert response.id is not None
    assert response.status == "in_progress"

    # Note: Actual retrieval would require a separate endpoint
    # or waiting for the task to complete, which is tested separately
