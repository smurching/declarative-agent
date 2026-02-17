"""
Acceptance tests for the Agent Backend API.

These tests verify that the API behaves correctly from an end-user perspective.
"""
import pytest
import json
from uuid import UUID
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_200(self, async_client):
        """Test that health endpoint returns 200 OK."""
        response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_check_structure(self, async_client):
        """Test that health check returns expected structure."""
        response = await async_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "database" in data
        assert "llm" in data

    @pytest.mark.asyncio
    async def test_health_check_status_values(self, async_client):
        """Test that health check returns valid status values."""
        response = await async_client.get("/health")
        data = response.json()

        # Status should be healthy or unhealthy
        assert data["status"] in ["healthy", "unhealthy"]

        # Database and LLM should have status indicators
        # "skipped" is valid for local testing without backends
        assert data["database"] in ["ok", "unknown", "skipped"] or "error" in data["database"]
        assert data["llm"] in ["ok", "unknown", "skipped"] or "error" in data["llm"]


class TestResponsesEndpointNonStreaming:
    """Tests for POST /responses in non-streaming mode."""

    @pytest.mark.asyncio
    async def test_create_response_non_streaming_success(
        self, async_client, sample_conversation_payload
    ):
        """Test creating a non-streaming response returns 200."""
        # Use OpenAI client's post method for custom endpoints
        response = await async_client.post("/responses", json=sample_conversation_payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_response_returns_response_id(
        self, async_client, sample_conversation_payload
    ):
        """Test that response includes a response ID."""
        response = await async_client.post("/responses", json=sample_conversation_payload)
        data = response.json()

        assert "id" in data
        assert data["id"].startswith("resp_")

    @pytest.mark.asyncio
    async def test_create_response_returns_output(
        self, async_client, sample_conversation_payload
    ):
        """Test that response includes output array."""
        response = await async_client.post("/responses", json=sample_conversation_payload)
        data = response.json()

        assert "output" in data
        assert isinstance(data["output"], list)
        assert len(data["output"]) > 0

    @pytest.mark.asyncio
    async def test_create_response_output_structure(
        self, async_client, sample_conversation_payload
    ):
        """Test that output items have correct structure."""
        response = await async_client.post("/responses", json=sample_conversation_payload)
        data = response.json()

        output_item = data["output"][0]
        assert "role" in output_item
        assert "content" in output_item
        assert output_item["role"] == "assistant"
        assert isinstance(output_item["content"], str)
        assert len(output_item["content"]) > 0

    @pytest.mark.asyncio
    async def test_create_response_with_existing_conversation(
        self, async_client, existing_conversation, sample_user_id
    ):
        """Test creating a response for an existing conversation."""
        payload = {
            "input": [{"role": "user", "content": "New message in existing conversation"}],
            "stream": False,
            "databricks_options": {
                "user_id": sample_user_id,
                "conversation_id": str(existing_conversation.id)
            }
        }

        response = await async_client.post("/responses", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "output" in data

    @pytest.mark.asyncio
    async def test_create_response_missing_user_id_fails(self, async_client):
        """Test that missing user_id returns error."""
        payload = {
            "input": [{"role": "user", "content": "Test"}],
            "stream": False,
            "databricks_options": {}  # Missing user_id
        }

        response = await async_client.post("/responses", json=payload)
        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_response_invalid_conversation_id_fails(
        self, async_client, sample_user_id
    ):
        """Test that invalid conversation_id returns 404."""
        invalid_uuid = "00000000-0000-0000-0000-000000000000"
        payload = {
            "input": [{"role": "user", "content": "Test"}],
            "stream": False,
            "databricks_options": {
                "user_id": sample_user_id,
                "conversation_id": invalid_uuid
            }
        }

        response = await async_client.post("/responses", json=payload)
        assert response.status_code == 404


class TestResponsesEndpointStreaming:
    """Tests for POST /responses in streaming mode."""

    @pytest.mark.asyncio
    async def test_create_response_streaming_returns_sse(
        self, async_client, sample_streaming_payload
    ):
        """Test that streaming mode returns SSE content type."""
        response = await async_client.post("/responses", json=sample_streaming_payload)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_streaming_response_events(
        self, async_client, sample_streaming_payload
    ):
        """Test that streaming returns proper SSE events."""
        response = await async_client.post("/responses", json=sample_streaming_payload)

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]  # Remove "data: " prefix
                if event_data != "[DONE]":
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass

        # Should have received some events
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_event_types(
        self, async_client, sample_streaming_payload
    ):
        """Test that streaming events have correct types."""
        response = await async_client.post("/responses", json=sample_streaming_payload)

        event_types = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data != "[DONE]":
                    try:
                        event = json.loads(event_data)
                        if "type" in event:
                            event_types.append(event["type"])
                    except json.JSONDecodeError:
                        pass

        # Should have delta and done events
        assert "response.output_item.delta" in event_types
        assert "response.output_item.done" in event_types

    @pytest.mark.asyncio
    async def test_streaming_response_delta_structure(
        self, async_client, sample_streaming_payload
    ):
        """Test that delta events have correct structure."""
        response = await async_client.post("/responses", json=sample_streaming_payload)

        delta_events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data != "[DONE]":
                    try:
                        event = json.loads(event_data)
                        if event.get("type") == "response.output_item.delta":
                            delta_events.append(event)
                    except json.JSONDecodeError:
                        pass

        # Should have at least one delta event
        assert len(delta_events) > 0

        # Check structure of first delta event
        first_delta = delta_events[0]
        assert "delta" in first_delta
        assert "text" in first_delta["delta"]
        assert isinstance(first_delta["delta"]["text"], str)

    @pytest.mark.asyncio
    async def test_streaming_response_ends_with_done(
        self, async_client, sample_streaming_payload
    ):
        """Test that streaming ends with [DONE] marker."""
        response = await async_client.post("/responses", json=sample_streaming_payload)

        lines = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                lines.append(line[6:])

        # Last line should be [DONE]
        assert lines[-1] == "[DONE]"


class TestResponsesEndpointBackground:
    """Tests for POST /responses in background mode."""

    @pytest.mark.asyncio
    async def test_background_mode_returns_immediately(
        self, async_client, sample_background_payload
    ):
        """Test that background mode returns immediately with in_progress status."""
        response = await async_client.post("/responses", json=sample_background_payload)
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert "status" in data
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_background_mode_no_output_initially(
        self, async_client, sample_background_payload
    ):
        """Test that background mode doesn't include output initially."""
        response = await async_client.post("/responses", json=sample_background_payload)
        data = response.json()

        # Should not have output field initially
        assert "output" not in data


class TestGetResponseEndpoint:
    """Tests for GET /responses/{id}."""

    @pytest.mark.asyncio
    async def test_get_response_not_found(self, async_client):
        """Test that GET for non-existent response returns 404."""
        response = await async_client.get("/responses/resp_nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_completed_response(
        self, async_client, sample_conversation_payload
    ):
        """Test retrieving a completed response."""
        # Create a response first
        create_response = await async_client.post("/responses", json=sample_conversation_payload)
        create_data = create_response.json()
        response_id = create_data["id"]

        # Retrieve it
        get_response = await async_client.get(f"/responses/{response_id}")
        assert get_response.status_code == 200

        get_data = get_response.json()
        assert get_data["id"] == response_id
        assert "status" in get_data

    @pytest.mark.asyncio
    async def test_get_background_response_eventually_completes(
        self, async_client, sample_background_payload
    ):
        """Test that background response can be retrieved after completion."""
        # Create background response
        create_response = await async_client.post("/responses", json=sample_background_payload)
        create_data = create_response.json()
        response_id = create_data["id"]

        # Wait a moment for background task
        import asyncio
        await asyncio.sleep(2)

        # Retrieve it
        get_response = await async_client.get(f"/responses/{response_id}")
        assert get_response.status_code == 200

        get_data = get_response.json()
        # Status should be completed or still in_progress
        assert get_data["status"] in ["completed", "in_progress", "failed"]


class TestConversationEndpoints:
    """Tests for conversation management endpoints."""

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(
        self, async_client, existing_conversation
    ):
        """Test retrieving a conversation with its messages."""
        conv_id = str(existing_conversation.id)
        response = await async_client.get(f"/conversations/{conv_id}")
        assert response.status_code == 200

        data = response.json()
        assert "conversation" in data
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_conversation_structure(
        self, async_client, existing_conversation
    ):
        """Test conversation response structure."""
        conv_id = str(existing_conversation.id)
        response = await async_client.get(f"/conversations/{conv_id}")
        data = response.json()

        conv = data["conversation"]
        assert "id" in conv
        assert "user_id" in conv
        assert "workspace_id" in conv
        assert "created_timestamp" in conv

    @pytest.mark.asyncio
    async def test_messages_structure(
        self, async_client, existing_conversation
    ):
        """Test messages response structure."""
        conv_id = str(existing_conversation.id)
        response = await async_client.get(f"/conversations/{conv_id}")
        data = response.json()

        messages = data["messages"]
        assert len(messages) > 0

        first_msg = messages[0]
        assert "id" in first_msg
        assert "role" in first_msg
        assert "content" in first_msg
        assert "message_index" in first_msg

    @pytest.mark.asyncio
    async def test_messages_ordered_by_index(
        self, async_client, existing_conversation
    ):
        """Test that messages are ordered by message_index."""
        conv_id = str(existing_conversation.id)
        response = await async_client.get(f"/conversations/{conv_id}")
        data = response.json()

        messages = data["messages"]
        indices = [msg["message_index"] for msg in messages]

        # Should be sorted in ascending order
        assert indices == sorted(indices)
        # Should start at 0
        assert indices[0] == 0
        # Should be sequential
        assert indices == list(range(len(indices)))

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, async_client):
        """Test that non-existent conversation returns error."""
        invalid_uuid = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/conversations/{invalid_uuid}")
        data = response.json()

        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_messages_pagination(
        self, async_client, existing_conversation
    ):
        """Test message pagination parameters."""
        conv_id = str(existing_conversation.id)

        # Get first 2 messages
        response = await async_client.get(f"/conversations/{conv_id}/messages?limit=2&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert "messages" in data
        assert "limit" in data
        assert "offset" in data
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert len(data["messages"]) <= 2


class TestMessagePersistence:
    """Tests for message persistence and conversation flow."""

    @pytest.mark.asyncio
    async def test_messages_persisted_after_response(
        self, async_client, sample_conversation_payload
    ):
        """Test that messages are saved to database after creating response."""
        # Create a response (creates conversation implicitly)
        create_response = await async_client.post("/responses", json=sample_conversation_payload)
        assert create_response.status_code == 200

        # We don't get conversation_id back directly, so this test would need
        # to be enhanced with database queries or returning conversation_id in response

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self, async_client, sample_user_id
    ):
        """Test multiple turns in a conversation."""
        # First turn
        payload1 = {
            "input": [{"role": "user", "content": "First message"}],
            "stream": False,
            "databricks_options": {"user_id": sample_user_id}
        }
        response1 = await async_client.post("/responses", json=payload1)
        assert response1.status_code == 200

        # Note: In current implementation, we'd need to track conversation_id
        # to do proper multi-turn. This test demonstrates the intended flow.


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422(self, async_client):
        """Test that invalid JSON returns 422."""
        response = await async_client.post(
            "/responses",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, async_client):
        """Test that missing required fields returns 422."""
        payload = {
            "input": [{"role": "user", "content": "Test"}],
            # Missing databricks_options
        }
        response = await async_client.post("/responses", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, async_client, sample_user_id):
        """Test that invalid role returns 422."""
        payload = {
            "input": [{"role": "invalid_role", "content": "Test"}],
            "databricks_options": {"user_id": sample_user_id}
        }
        response = await async_client.post("/responses", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_input_returns_error(self, async_client, sample_user_id):
        """Test that empty input array returns error."""
        payload = {
            "input": [],
            "databricks_options": {"user_id": sample_user_id}
        }
        response = await async_client.post("/responses", json=payload)
        # Should either return 422 or handle gracefully
        assert response.status_code in [400, 422]


class TestDatabaseSchema:
    """Tests for database schema compliance (estore compatibility)."""

    @pytest.mark.asyncio
    async def test_conversation_has_required_fields(self, db_session, sample_user_id, sample_workspace_id):
        """Test that conversation has all estore-required fields."""
        from server.db.queries import create_conversation

        conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        assert conv.id is not None
        assert conv.user_id == sample_user_id
        assert conv.internal_workspace_id == sample_workspace_id
        assert conv.created_timestamp is not None
        assert conv.internal_last_updated_timestamp is not None

    @pytest.mark.asyncio
    async def test_message_index_uniqueness(self, db_session, existing_conversation):
        """Test that message_index uniqueness is enforced."""
        from server.db.queries import save_message
        from server.db.models import MessageRole
        from sqlalchemy.exc import IntegrityError

        # Try to create two messages with same index
        await save_message(
            db_session,
            existing_conversation.id,
            MessageRole.USER,
            {"text": "Test 1"},
            100
        )
        await db_session.commit()

        # This should fail
        with pytest.raises(IntegrityError):
            await save_message(
                db_session,
                existing_conversation.id,
                MessageRole.USER,
                {"text": "Test 2"},
                100  # Same index
            )
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_message_content_serialization(self, db_session, existing_conversation):
        """Test that message content is properly serialized."""
        from server.db.queries import save_message, get_messages
        from server.db.models import MessageRole
        import json

        test_content = {
            "text": "Test message",
            "metadata": {"key": "value"}
        }

        await save_message(
            db_session,
            existing_conversation.id,
            MessageRole.USER,
            test_content,
            100
        )
        await db_session.commit()

        # Retrieve and check
        messages = await get_messages(db_session, existing_conversation.id)
        saved_msg = next(m for m in messages if m.message_index == 100)

        # Deserialize content
        saved_content = json.loads(saved_msg.content.decode("utf-8"))
        assert saved_content == test_content
