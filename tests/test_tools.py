"""Tests for hosted tools support in /responses endpoint."""

import pytest
from openai import AsyncOpenAI


@pytest.fixture
def sample_user_id() -> int:
    """Provide a sample user ID for tests."""
    return 12345


@pytest.fixture
async def openai_client():
    """Provide OpenAI client for testing."""
    client = AsyncOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",
    )
    try:
        yield client
    finally:
        await client.close()


class TestHostedTools:
    """Tests for hosted tools (tools executed by the backend)."""

    @pytest.mark.asyncio
    async def test_request_with_tools_parameter(self, openai_client, sample_user_id):
        """Test that tools can be included in the request."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What time is it?"}],
            stream=False,
            tools=[{"type": "get_current_time"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id.startswith("resp_")
        assert response.status == "completed"
        assert response.output is not None

    @pytest.mark.asyncio
    async def test_llm_can_call_get_current_time_tool(self, openai_client, sample_user_id):
        """Test that LLM can call the get_current_time tool."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is the current time?"}],
            stream=False,
            tools=[{"type": "get_current_time"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Response should include time information
        assert response.output is not None
        output_text = response.output[0].content.lower()
        # Should mention time-related keywords
        assert any(keyword in output_text for keyword in ["time", "clock", "hour", "minute"])

    @pytest.mark.asyncio
    async def test_llm_can_call_calculator_tool(self, openai_client, sample_user_id):
        """Test that LLM can call the calculator tool."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 123 + 456?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Response should include the correct calculation
        assert response.output is not None
        output_text = response.output[0].content
        # Should include the result (579)
        assert "579" in output_text

    @pytest.mark.asyncio
    async def test_multiple_tools_available(self, openai_client, sample_user_id):
        """Test that multiple tools can be provided."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What time is it and what is 10 + 20?"}],
            stream=False,
            tools=[
                {"type": "get_current_time"},
                {"type": "calculator"}
            ],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        output_text = response.output[0].content.lower()
        # Should mention both time and calculation
        assert any(keyword in output_text for keyword in ["time", "clock"])
        assert "30" in output_text  # The calculation result

    @pytest.mark.asyncio
    async def test_streaming_with_tools(self, openai_client, sample_user_id):
        """Test that tools work with streaming mode."""
        stream = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 50 * 2?"}],
            stream=True,
            tools=[{"type": "calculator"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        # Collect all events
        events = []
        async for event in stream:
            events.append(event)

        # Should have received events
        assert len(events) > 0
        # Final output should include the calculation result (100)
        # (check accumulated text or final event)

    @pytest.mark.asyncio
    async def test_background_mode_with_tools(self, openai_client, sample_user_id):
        """Test that tools work with background mode."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 999 + 1?"}],
            background=True,
            tools=[{"type": "calculator"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id.startswith("resp_")
        assert response.status == "in_progress"

        # Wait and retrieve
        import asyncio
        await asyncio.sleep(2)

        result = await openai_client.responses.retrieve(response.id)
        assert result.status in ["completed", "in_progress"]

    @pytest.mark.asyncio
    async def test_no_tools_provided(self, openai_client, sample_user_id):
        """Test that request works without tools (backward compatibility)."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Hello"}],
            stream=False,
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.id.startswith("resp_")
        assert response.status == "completed"

    @pytest.mark.asyncio
    async def test_tool_use_persisted_in_conversation(self, openai_client, sample_user_id):
        """Test that tool calls are persisted in conversation history."""
        # First message with tool use
        response1 = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 5 + 5?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        conversation_id = response1.conversation_id

        # Follow-up message referencing previous calculation
        response2 = await openai_client.responses.create(
            input=[{"role": "user", "content": "Now multiply that by 2"}],
            stream=False,
            tools=[{"type": "calculator"}],
            extra_body={
                "databricks_options": {
                    "user_id": sample_user_id,
                    "conversation_id": conversation_id
                }
            }
        )

        # Should correctly reference previous result (10) and multiply by 2 = 20
        output_text = response2.output[0].content
        assert "20" in output_text

    @pytest.mark.asyncio
    async def test_invalid_tool_type_returns_error(self, openai_client, sample_user_id):
        """Test that invalid tool types return proper error."""
        from openai import UnprocessableEntityError

        with pytest.raises(UnprocessableEntityError) as exc_info:
            await openai_client.responses.create(
                input=[{"role": "user", "content": "Test"}],
                stream=False,
                tools=[{"type": "nonexistent_tool"}],
                extra_body={"databricks_options": {"user_id": sample_user_id}}
            )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_weather_tool(self, openai_client, sample_user_id):
        """Test the weather tool (mock implementation)."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What's the weather in San Francisco?"}],
            stream=False,
            tools=[{"type": "get_weather"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        output_text = response.output[0].content.lower()
        # Should mention weather-related information
        assert any(keyword in output_text for keyword in ["weather", "temperature", "sunny", "cloudy"])


class TestToolChoiceParameter:
    """Tests for tool_choice parameter to control tool usage."""

    @pytest.mark.asyncio
    async def test_tool_choice_auto(self, openai_client, sample_user_id):
        """Test tool_choice='auto' - LLM decides whether to use tools."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "Hello, how are you?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            tool_choice="auto",  # LLM should choose not to use calculator for greeting
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        # Should respond normally without using calculator

    @pytest.mark.asyncio
    async def test_tool_choice_required(self, openai_client, sample_user_id):
        """Test tool_choice='required' - LLM must use a tool."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 10 + 20?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            tool_choice="required",  # Must use a tool
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        # Should have used the calculator tool

    @pytest.mark.asyncio
    async def test_tool_choice_none(self, openai_client, sample_user_id):
        """Test tool_choice='none' - LLM should not use tools."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 5 + 5?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            tool_choice="none",  # Should not use tools
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        # Should respond without using the calculator (might estimate or refuse)


class TestToolResponseFormat:
    """Tests for tool call/response format in conversation history."""

    @pytest.mark.asyncio
    async def test_tool_call_in_message_history(self, openai_client, sample_user_id):
        """Test that tool calls appear in message history."""
        response = await openai_client.responses.create(
            input=[{"role": "user", "content": "What is 7 * 8?"}],
            stream=False,
            tools=[{"type": "calculator"}],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        conversation_id = response.conversation_id

        # Retrieve conversation to check message history
        import httpx
        async with httpx.AsyncClient() as client:
            conv_response = await client.get(
                f"http://localhost:8000/conversations/{conversation_id}"
            )
            data = conv_response.json()

        messages = data["messages"]

        # Should have:
        # 1. User message
        # 2. Assistant message (possibly with tool_calls)
        # 3. Tool response (if tool was called)
        # 4. Final assistant message with result

        assert len(messages) >= 2  # At minimum user + assistant

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, openai_client, sample_user_id):
        """Test that LLM can make multiple tool calls in parallel."""
        response = await openai_client.responses.create(
            input=[{
                "role": "user",
                "content": "What is 10+20, 5*6, and the current time?"
            }],
            stream=False,
            tools=[
                {"type": "calculator"},
                {"type": "get_current_time"}
            ],
            extra_body={"databricks_options": {"user_id": sample_user_id}}
        )

        assert response.output is not None
        output_text = response.output[0].content

        # Should include all three results
        assert "30" in output_text  # 10+20
        # Note: LLM might break down 5*6 into multiple steps or calculate directly
