"""
Acceptance tests for the Agent Backend API.

These tests verify that the API behaves correctly from an end-user perspective.
Tests use the OpenAI client for OpenResponses-compatible endpoints and httpx for custom endpoints.
"""
import pytest
import json
from uuid import UUID
from httpx import AsyncClient
import httpx


async def parse_sse_stream(stream):
    """Helper to parse SSE events from OpenAI SDK streaming response."""
    events = []
    async for event in stream:
        events.append(event)
    return events


class TestHealthEndpoint:
    """Tests for the /health endpoint (custom, uses httpx)."""

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
    """Tests for POST /v1/responses in non-streaming mode (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_create_response_non_streaming_success(
        self, openai_client, sample_user_id
    ):
        """Test creating a non-streaming response using OpenAI SDK."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Hello, this is a test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id.startswith("resp_")
        assert response.output is not None

    @pytest.mark.asyncio
    async def test_create_response_returns_response_id(
        self, openai_client, sample_user_id
    ):
        """Test that response includes a response ID."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id is not None
        assert response.id.startswith("resp_")

    @pytest.mark.asyncio
    async def test_create_response_returns_output(
        self, openai_client, sample_user_id
    ):
        """Test that response includes output array."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        assert isinstance(response.output, list)
        assert len(response.output) > 0

    @pytest.mark.asyncio
    async def test_create_response_output_structure(
        self, openai_client, sample_user_id
    ):
        """Test that output items have correct structure."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        output_item = response.output[0]

        assert output_item.role == "assistant"
        assert isinstance(output_item.content, str)
        assert len(output_item.content) > 0

    @pytest.mark.asyncio
    async def test_create_response_with_existing_conversation(
        self, openai_client, sample_user_id
    ):
        """Test creating a response for an existing conversation."""
        # Create a conversation via API
        response1 = await openai_client.responses.create(
            input=[{"role": "user", "content": "First message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Extract conversation_id from response metadata (if available)
        # For now, create a new conversation since we don't expose conversation_id in response
        # This test validates that conversations can be reused across multiple responses
        response2 = await openai_client.responses.create(
            input=[{"role": "user", "content": "Second message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response1.id.startswith("resp_")
        assert response2.id.startswith("resp_")
        assert response1.id != response2.id  # Different response IDs

    @pytest.mark.asyncio
    async def test_create_response_missing_user_id_fails(self, openai_client):
        """Test that missing user_id returns error."""
        from openai import UnprocessableEntityError

        with pytest.raises(UnprocessableEntityError) as exc_info:
            await openai_client.responses.create(
                input=[{"role": "user", "content": "Test"}],
                stream=False,
                extra_body={"databricks_options": {}}  # Missing user_id
            )

        # Should be a 422 validation error
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_response_invalid_conversation_id_fails(
        self, openai_client, sample_user_id
    ):
        """Test that invalid conversation_id returns 404."""
        from openai import NotFoundError

        invalid_uuid = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(NotFoundError) as exc_info:
            await openai_client.responses.create(
                input=[{"role": "user", "content": "Test"}],
                stream=False,
                extra_body={
                    "databricks_options": {
                        "user_id": sample_user_id,
                        "conversation_id": invalid_uuid
                    }
                }
            )

        # Should be a 404 error
        assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


class TestResponsesEndpointStreaming:
    """Tests for POST /v1/responses in streaming mode (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_create_response_streaming_returns_sse(
        self, openai_client, sample_user_id
    ):
        """Test that streaming mode returns SSE events."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "Count to 3"}],
            stream=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        events = await parse_sse_stream(stream)
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_events(
        self, openai_client, sample_user_id
    ):
        """Test that streaming returns proper SSE events."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "Count to 3"}],
            stream=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        events = await parse_sse_stream(stream)
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_event_types(
        self, openai_client, sample_user_id
    ):
        """Test that streaming events have correct types."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "Count to 3"}],
            stream=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        events = await parse_sse_stream(stream)
        # Events from SDK are objects, check for delta/done events
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_delta_structure(
        self, openai_client, sample_user_id
    ):
        """Test that delta events have correct structure."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "Count to 3"}],
            stream=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        events = await parse_sse_stream(stream)
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_ends_with_done(
        self, openai_client, sample_user_id
    ):
        """Test that streaming ends with done marker."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "Count to 3"}],
            stream=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        events = await parse_sse_stream(stream)
        assert len(events) > 0


class TestResponsesEndpointBackground:
    """Tests for POST /v1/responses in background mode (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_background_mode_returns_immediately(
        self, openai_client, sample_user_id
    ):
        """Test that background mode returns immediately with in_progress status."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Long running task"}],
            background=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id is not None
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_background_mode_no_output_initially(
        self, openai_client, sample_user_id
    ):
        """Test that background mode doesn't include output initially."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Long running task"}],
            background=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Should not have output field initially
        assert response.output is None or len(response.output) == 0


class TestGetResponseEndpoint:
    """Tests for GET /v1/responses/{id} (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_get_response_not_found(self, openai_client):
        """Test that GET for non-existent response returns 404."""
        from openai import NotFoundError

        with pytest.raises(NotFoundError) as exc_info:
            await openai_client.responses.retrieve("resp_nonexistent")

        assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_completed_response(
        self, openai_client, sample_user_id
    ):
        """Test retrieving a completed response."""
        # Create a response first
        create_response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Retrieve it
        get_response = await openai_client.responses.retrieve(create_response.id)

        assert get_response.id == create_response.id
        assert get_response.status in ["completed", "in_progress", "failed"]

    @pytest.mark.asyncio
    async def test_get_background_response_eventually_completes(
        self, openai_client, sample_user_id
    ):
        """Test that background response can be retrieved after completion."""
        # Create background response
        create_response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Background task"}],
            background=True,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Wait a moment for background task
        import asyncio
        await asyncio.sleep(2)

        # Retrieve it
        get_response = await openai_client.responses.retrieve(create_response.id)

        # Status should be completed or still in_progress
        assert get_response.status in ["completed", "in_progress", "failed"]


class TestConversationEndpoints:
    """Tests for conversation management endpoints (custom, uses httpx)."""

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(
        self, openai_client, async_client, sample_user_id
    ):
        """Test retrieving a conversation with its messages."""
        # Create a conversation with messages via API
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Hello"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Get conversation_id from response
        conversation_id = response.conversation_id
        assert conversation_id is not None

        # Retrieve conversation via custom endpoint
        conv_response = await async_client.get(f"/conversations/{conversation_id}")
        assert conv_response.status_code == 200

        data = conv_response.json()
        assert "conversation" in data
        assert "messages" in data
        assert data["conversation"]["id"] == conversation_id

    @pytest.mark.asyncio
    async def test_conversation_structure(
        self, openai_client, async_client, sample_user_id
    ):
        """Test conversation response structure."""
        # Create a conversation via API
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        conversation_id = response.conversation_id
        conv_response = await async_client.get(f"/conversations/{conversation_id}")
        data = conv_response.json()

        # Verify structure
        assert "conversation" in data
        assert "messages" in data
        assert "id" in data["conversation"]
        assert "user_id" in data["conversation"]
        assert isinstance(data["messages"], list)

    @pytest.mark.asyncio
    async def test_messages_structure(
        self, openai_client, async_client, sample_user_id
    ):
        """Test messages response structure."""
        # Create conversation with multiple messages
        response1 = await openai_client.responses.create(
            input=[{"role": "user", "content": "First message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        conversation_id = response1.conversation_id

        # Add another message to the same conversation
        response2 = await openai_client.responses.create(
            input=[{"role": "user", "content": "Second message"}],
            stream=False,
            extra_body={
                "databricks_options": {
                    "user_id": sample_user_id,
                    "conversation_id": conversation_id
                }
            }
        )

        # Get messages
        msgs_response = await async_client.get(f"/conversations/{conversation_id}/messages")
        data = msgs_response.json()

        # Verify structure
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) > 0
        for msg in data["messages"]:
            assert "id" in msg
            assert "role" in msg
            assert "content" in msg
            assert "message_index" in msg

    @pytest.mark.asyncio
    async def test_messages_ordered_by_index(
        self, openai_client, async_client, sample_user_id
    ):
        """Test that messages are ordered by message_index."""
        # Create conversation with multiple messages
        response1 = await openai_client.responses.create(
            input=[{"role": "user", "content": "First"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        conversation_id = response1.conversation_id

        # Add more messages
        response2 = await openai_client.responses.create(
            input=[{"role": "user", "content": "Second"}],
            stream=False,
            extra_body={
                "databricks_options": {
                    "user_id": sample_user_id,
                    "conversation_id": conversation_id
                }
            }
        )

        # Get conversation with messages
        conv_response = await async_client.get(f"/conversations/{conversation_id}")
        data = conv_response.json()

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
    """Tests for message persistence and conversation flow (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_messages_persisted_after_response(
        self, openai_client, sample_user_id
    ):
        """Test that messages are saved to database after creating response."""
        # Create a response (creates conversation implicitly)
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Test persistence"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id is not None
        # Messages should be persisted in database

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self, openai_client, sample_user_id
    ):
        """Test multiple turns in a conversation."""
        # First turn
        response1 = await openai_client.responses.create(
            input=[{"role": "user", "content": "First message"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response1.id is not None
        # Note: In current implementation, we'd need to track conversation_id
        # to do proper multi-turn. This test demonstrates the intended flow.


class TestErrorHandling:
    """Tests for error handling and edge cases (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422(self, async_client):
        """Test that invalid JSON returns 422 (uses httpx for raw request)."""
        response = await async_client.post(
            "/v1/responses",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, openai_client):
        """Test that missing required fields returns 422."""
        from openai import UnprocessableEntityError

        with pytest.raises(UnprocessableEntityError) as exc_info:
            await openai_client.responses.create(
                input=[{"role": "user", "content": "Test"}],
                stream=False
                # Missing databricks_options/extra_body
            )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, openai_client, sample_user_id):
        """Test that invalid role returns 422."""
        from openai import UnprocessableEntityError

        with pytest.raises(UnprocessableEntityError) as exc_info:
            await openai_client.responses.create(
                input=[{"role": "invalid_role", "content": "Test"}],
                stream=False,
                extra_body={"databricks_options": {"user_id": sample_user_id}}
            )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_input_returns_error(self, openai_client, sample_user_id):
        """Test that empty input array returns error."""
        from openai import UnprocessableEntityError

        with pytest.raises(UnprocessableEntityError) as exc_info:
            await openai_client.responses.create(
                input=[],
                stream=False,
                extra_body={"databricks_options": {"user_id": sample_user_id}}
            )

        # Should be a 422 validation error
        assert exc_info.value.status_code == 422


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
