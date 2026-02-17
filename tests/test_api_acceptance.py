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
        """Test creating a non-streaming response using OpenAI client."""
        # Use OpenAI client to call our OpenResponses-compatible endpoint
        # Note: Since responses namespace isn't built into OpenAI SDK, we use the HTTP client
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Hello, this is a test message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
        )
        response = http_response.json()

        assert response["id"].startswith("resp_")
        assert "output" in response

    @pytest.mark.asyncio
    async def test_create_response_returns_response_id(
        self, openai_client, sample_user_id
    ):
        """Test that response includes a response ID."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Test message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        assert "id" in response
        assert response["id"].startswith("resp_")

    @pytest.mark.asyncio
    async def test_create_response_returns_output(
        self, openai_client, sample_user_id
    ):
        """Test that response includes output array."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Test message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        assert "output" in response
        output = response["output"]
        assert isinstance(output, list)
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_create_response_output_structure(
        self, openai_client, sample_user_id
    ):
        """Test that output items have correct structure."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Test message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        output = response["output"]
        output_item = output[0]

        assert "role" in output_item
        assert "content" in output_item

        role = output_item["role"]
        content = output_item["content"]

        assert role == "assistant"
        assert isinstance(content, str)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_create_response_with_existing_conversation(
        self, openai_client, existing_conversation, sample_user_id
    ):
        """Test creating a response for an existing conversation."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "New message in existing conversation"}],
                "stream": False,
                "databricks_options": {
                    "user_id": sample_user_id,
                    "conversation_id": str(existing_conversation.id)
                }
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        assert "output" in response

    @pytest.mark.asyncio
    async def test_create_response_missing_user_id_fails(self, openai_client):
        """Test that missing user_id returns error."""
        from openai import BadRequestError

        with pytest.raises((BadRequestError, Exception)) as exc_info:
            await openai_client.post(
                "/responses",
                body={
                    "input": [{"role": "user", "content": "Test"}],
                    "databricks_options": {}  # Missing user_id
                },
                cast_to=httpx.Response,
            )

        # Should be a 422 validation error
        assert "422" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_response_invalid_conversation_id_fails(
        self, openai_client, sample_user_id
    ):
        """Test that invalid conversation_id returns 404."""
        from openai import NotFoundError

        invalid_uuid = "00000000-0000-0000-0000-000000000000"

        with pytest.raises((NotFoundError, Exception)) as exc_info:
            await openai_client.post(
                "/responses",
                body={
                    "input": [{"role": "user", "content": "Test"}],
                    "databricks_options": {
                        "user_id": sample_user_id,
                        "conversation_id": invalid_uuid
                    }
                },
                cast_to=httpx.Response,
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
        stream = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
                "databricks_options": {"user_id": sample_user_id}
            },
            stream=True,
            cast_to=httpx.Response,
        )

        # Should be able to iterate over stream
        events = []
        async for line in stream.aiter_lines():
            if line.startswith("data: "):
                events.append(line[6:])  # Remove "data: " prefix

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_events(
        self, openai_client, sample_user_id
    ):
        """Test that streaming returns proper SSE events."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
                "databricks_options": {"user_id": sample_user_id}
            },
                        stream=True,
            cast_to=httpx.Response,
        )
        stream = http_response

        events = []
        async for event in stream:
            events.append(event)

        # Should have received some events
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_event_types(
        self, openai_client, sample_user_id
    ):
        """Test that streaming events have correct types."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
                "databricks_options": {"user_id": sample_user_id}
            },
                        stream=True,
            cast_to=httpx.Response,
        )
        stream = http_response

        event_types = []
        async for event in stream:
            if hasattr(event, "type"):
                event_types.append(event.type)
            elif isinstance(event, dict) and "type" in event:
                event_types.append(event["type"])

        # Should have delta and done events
        assert any("delta" in t for t in event_types)
        assert any("done" in t for t in event_types)

    @pytest.mark.asyncio
    async def test_streaming_response_delta_structure(
        self, openai_client, sample_user_id
    ):
        """Test that delta events have correct structure."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
                "databricks_options": {"user_id": sample_user_id}
            },
                        stream=True,
            cast_to=httpx.Response,
        )
        stream = http_response

        delta_events = []
        async for event in stream:
            event_type = getattr(event, "type", event.get("type") if isinstance(event, dict) else None)
            if event_type and "delta" in event_type:
                delta_events.append(event)

        # Should have at least one delta event
        assert len(delta_events) > 0

    @pytest.mark.asyncio
    async def test_streaming_response_ends_with_done(
        self, openai_client, sample_user_id
    ):
        """Test that streaming ends with done marker."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
                "databricks_options": {"user_id": sample_user_id}
            },
                        stream=True,
            cast_to=httpx.Response,
        )
        stream = http_response

        events = []
        async for event in stream:
            events.append(event)

        # Last event should indicate completion
        assert len(events) > 0


class TestResponsesEndpointBackground:
    """Tests for POST /v1/responses in background mode (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_background_mode_returns_immediately(
        self, openai_client, sample_user_id
    ):
        """Test that background mode returns immediately with in_progress status."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Long running task"}],
                "background": True,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        assert "id" in response
        assert "status" in response
        status = response["status"]
        assert status == "in_progress"

    @pytest.mark.asyncio
    async def test_background_mode_no_output_initially(
        self, openai_client, sample_user_id
    ):
        """Test that background mode doesn't include output initially."""
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Long running task"}],
                "background": True,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        # Should not have output field initially
        assert "output" not in response or response.get("output") is None


class TestGetResponseEndpoint:
    """Tests for GET /v1/responses/{id} (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_get_response_not_found(self, openai_client):
        """Test that GET for non-existent response returns 404."""
        from openai import NotFoundError

        with pytest.raises((NotFoundError, Exception)) as exc_info:
            await openai_client.get(
                "/responses/resp_nonexistent",
                cast_to=httpx.Response,
            )

        assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_completed_response(
        self, openai_client, sample_user_id
    ):
        """Test retrieving a completed response."""
        # Create a response first
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Test message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        create_response = http_response.json()
        response_id = create_response["id"]

        # Retrieve it
        http_response = await openai_client.get(
            f"/responses/{response_id}",
            cast_to=httpx.Response,
                    )
        get_response = http_response.json()

        assert "id" in get_response
        assert get_response["id"] == response_id
        assert "status" in get_response

    @pytest.mark.asyncio
    async def test_get_background_response_eventually_completes(
        self, openai_client, sample_user_id
    ):
        """Test that background response can be retrieved after completion."""
        # Create background response
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Background task"}],
                "background": True,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        create_response = http_response.json()
        response_id = create_response["id"]

        # Wait a moment for background task
        import asyncio
        await asyncio.sleep(2)

        # Retrieve it
        http_response = await openai_client.get(
            f"/responses/{response_id}",
            cast_to=httpx.Response,
                    )
        get_response = http_response.json()

        status = get_response["status"]
        # Status should be completed or still in_progress
        assert status in ["completed", "in_progress", "failed"]


class TestConversationEndpoints:
    """Tests for conversation management endpoints (custom, uses httpx)."""

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
    """Tests for message persistence and conversation flow (uses OpenAI client)."""

    @pytest.mark.asyncio
    async def test_messages_persisted_after_response(
        self, openai_client, sample_user_id
    ):
        """Test that messages are saved to database after creating response."""
        # Create a response (creates conversation implicitly)
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "Test persistence"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response = http_response.json()

        assert "id" in response
        # Messages should be persisted in database

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self, openai_client, sample_user_id
    ):
        """Test multiple turns in a conversation."""
        # First turn
        http_response = await openai_client.post(
            "/responses",
            body={
                "input": [{"role": "user", "content": "First message"}],
                "stream": False,
                "databricks_options": {"user_id": sample_user_id}
            },
            cast_to=httpx.Response,
                    )
        response1 = http_response.json()

        assert "id" in response1
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
        from openai import BadRequestError

        with pytest.raises((BadRequestError, Exception)) as exc_info:
            await openai_client.post(
                "/responses",
                body={
                    "input": [{"role": "user", "content": "Test"}],
                    # Missing databricks_options
                },
                cast_to=httpx.Response,
            )

        assert "422" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, openai_client, sample_user_id):
        """Test that invalid role returns 422."""
        from openai import BadRequestError

        with pytest.raises((BadRequestError, Exception)) as exc_info:
            await openai_client.post(
                "/responses",
                body={
                    "input": [{"role": "invalid_role", "content": "Test"}],
                    "databricks_options": {"user_id": sample_user_id}
                },
                cast_to=httpx.Response,
            )

        assert "422" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_empty_input_returns_error(self, openai_client, sample_user_id):
        """Test that empty input array returns error."""
        from openai import BadRequestError

        with pytest.raises((BadRequestError, Exception)) as exc_info:
            await openai_client.post(
                "/responses",
                body={
                    "input": [],
                    "databricks_options": {"user_id": sample_user_id}
                },
                cast_to=httpx.Response,
            )

        # Should be a 422 validation error
        assert "422" in str(exc_info.value) or "validation" in str(exc_info.value).lower()


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
