"""OpenResponses-compatible /responses endpoint."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from uuid import uuid4
import json
import logging
import asyncio
from typing import List, Dict

from server.schemas.responses import (
    ResponsesRequest,
    ResponsesResponse,
    BackgroundResponse,
    RetrieveResponseResponse,
    OutputItem,
    DatabricksOptions,
    InputMessage,
)
from server.db.connection import get_db_context
from server.db.queries import (
    create_conversation,
    get_conversation,
    get_next_message_index,
    save_message,
    create_response_record,
    get_response_record,
    update_response_progress,
    update_response_status,
    get_messages,
)
from server.db.models import MessageRole, ResponseStatus
from server.llm.client import stream_llm_response, generate_response
from server.config import get_settings

logger = logging.getLogger(__name__)
responses_router = APIRouter(prefix="/v1")


def _convert_input_messages(input_messages: list) -> List[Dict[str, str]]:
    """Convert OpenResponses input format to OpenAI format."""
    return [{"role": msg.role, "content": msg.content} for msg in input_messages]


async def _stream_openresponses_events(
    response_id: str,
    conversation_id,
    input_messages: list,  # Messages for LLM (may include history)
    new_user_message: dict = None,  # Just the new user message to save
    model: str = None,
    temperature: float = 0.7,
):
    """
    Generate SSE stream in OpenResponses format.

    Yields SSE events as the LLM generates a response.

    Args:
        input_messages: All messages to send to LLM (including history if applicable)
        new_user_message: The new user message to save to DB (None if already saved)
    """
    try:
        # Save new user message if provided (not already in DB)
        if new_user_message:
            async with get_db_context() as session:
                message_index = await get_next_message_index(session, conversation_id)
                user_content = {"text": new_user_message.content}
                await save_message(
                    session,
                    conversation_id,
                    MessageRole.USER,
                    user_content,
                    message_index,
                )
                await session.commit()

        # Convert messages to OpenAI format
        llm_messages = _convert_input_messages(input_messages)

        # Stream LLM response
        response_text = ""
        async for chunk in stream_llm_response(llm_messages, model, temperature):
            response_text += chunk

            # Send delta event (OpenResponses format)
            event = {
                "type": "response.output_text.delta",
                "delta": chunk,
            }
            yield f"data: {json.dumps(event)}\n\n"

            # Periodically save progress for resumption
            if len(response_text) % 100 < len(chunk):
                async with get_db_context() as session:
                    await update_response_progress(session, response_id, response_text)
                    await session.commit()

        # Save assistant message
        async with get_db_context() as session:
            message_index = await get_next_message_index(session, conversation_id)
            assistant_content = {"text": response_text}
            await save_message(
                session,
                conversation_id,
                MessageRole.ASSISTANT,
                assistant_content,
                message_index,
            )
            await session.commit()

        # Send done event
        done_event = {
            "type": "response.output_item.done",
            "item": {"role": "assistant", "content": response_text},
        }
        yield f"data: {json.dumps(done_event)}\n\n"
        yield "data: [DONE]\n\n"

        # Mark response complete
        async with get_db_context() as session:
            final_output = [{"role": "assistant", "content": response_text}]
            await update_response_status(
                session,
                response_id,
                ResponseStatus.COMPLETED,
                final_output=final_output,
            )
            await session.commit()

    except Exception as e:
        logger.exception(f"Error streaming response: {e}")

        # Mark response as failed
        async with get_db_context() as session:
            await update_response_status(
                session,
                response_id,
                ResponseStatus.FAILED,
                error_message=str(e),
            )
            await session.commit()

        # Send error event
        error_event = {
            "type": "response.error",
            "error": {"message": str(e)},
        }
        yield f"data: {json.dumps(error_event)}\n\n"


async def _execute_response_background(
    response_id: str,
    conversation_id,
    input_messages: list,  # Messages for LLM (may include history)
    new_user_message: dict = None,  # Just the new user message to save
    model: str = None,
    temperature: float = 0.7,
):
    """Execute response in background mode."""
    try:
        # Save new user message if provided
        if new_user_message:
            async with get_db_context() as session:
                message_index = await get_next_message_index(session, conversation_id)
                user_content = {"text": new_user_message.content}
                await save_message(
                    session,
                    conversation_id,
                    MessageRole.USER,
                    user_content,
                    message_index,
                )
                await session.commit()

        # Generate response (non-streaming)
        llm_messages = _convert_input_messages(input_messages)
        response = await generate_response(llm_messages, stream=False, model=model, temperature=temperature)
        # Extract text from OpenResponses format
        response_text = response.output[0].content[0].text

        # Save assistant message
        async with get_db_context() as session:
            message_index = await get_next_message_index(session, conversation_id)
            assistant_content = {"text": response_text}
            await save_message(
                session,
                conversation_id,
                MessageRole.ASSISTANT,
                assistant_content,
                message_index,
            )
            await session.commit()

        # Mark complete
        async with get_db_context() as session:
            final_output = [{"role": "assistant", "content": response_text}]
            await update_response_status(
                session,
                response_id,
                ResponseStatus.COMPLETED,
                final_output=final_output,
            )
            await session.commit()

    except Exception as e:
        logger.exception(f"Error in background response: {e}")
        async with get_db_context() as session:
            await update_response_status(
                session,
                response_id,
                ResponseStatus.FAILED,
                error_message=str(e),
            )
            await session.commit()


@responses_router.post("/responses")
async def handle_responses(request: ResponsesRequest):
    """
    POST /v1/responses - OpenAI-compatible endpoint.

    Supports streaming, non-streaming, and background modes.
    Compatible with OpenAI SDK's client.responses.create() method.
    """
    settings = get_settings()

    # Validate input is not empty
    if isinstance(request.input, str):
        if not request.input.strip():
            raise HTTPException(status_code=422, detail="Input cannot be empty")
        # Single string input - convert to user message
        from server.schemas.responses import InputMessage
        input_messages = [InputMessage(role="user", content=request.input)]
    else:
        if not request.input:
            raise HTTPException(status_code=422, detail="Input cannot be empty")
        input_messages = request.input

    # Validate databricks_options and user_id
    if not request.databricks_options:
        raise HTTPException(status_code=422, detail="databricks_options is required")

    databricks_opts = request.databricks_options
    if databricks_opts.user_id is None or databricks_opts.user_id == 0:
        raise HTTPException(status_code=422, detail="databricks_options.user_id is required")

    # Get or create conversation
    async with get_db_context() as session:
        if databricks_opts.conversation_id:
            conv = await get_conversation(session, databricks_opts.conversation_id)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Load conversation history to include in LLM context
            from server.db.queries import get_messages
            import json
            messages = await get_messages(session, conv.id)
            history = []
            for msg in messages:
                content_dict = json.loads(msg.content.decode("utf-8"))
                history.append({
                    "role": msg.role.lower() if hasattr(msg.role, 'lower') else msg.role.value.lower(),
                    "content": content_dict.get("text", str(content_dict))
                })

            # Create messages with history for LLM (don't modify input_messages)
            messages_with_history = history + input_messages
        else:
            # No history for new conversations
            messages_with_history = input_messages
        else:
            conv = await create_conversation(
                session,
                databricks_opts.user_id,
                settings.workspace_id,
            )
        await session.commit()

    # Create response record
    response_id = f"resp_{uuid4().hex[:12]}"
    async with get_db_context() as session:
        await create_response_record(
            session,
            response_id,
            conv.id,
            request.background,
        )
        await session.commit()

    if request.background:
        # Start background task and return immediately
        asyncio.create_task(
            _execute_response_background(
                response_id,
                conv.id,
                messages_with_history,  # Use history-aware messages for LLM
                input_messages[-1],  # Only the new user message to save
                request.model,
                request.temperature,
            )
        )
        return BackgroundResponse(
            id=response_id,
            status="in_progress",
            conversation_id=str(conv.id)
        )

    elif request.stream:
        # Stream response
        return StreamingResponse(
            _stream_openresponses_events(
                response_id,
                conv.id,
                messages_with_history,  # Use history-aware messages for LLM
                input_messages[-1],  # Only the new user message to save
                request.model,
                request.temperature,
            ),
            media_type="text/event-stream",
        )

    else:
        # Non-streaming response
        async with get_db_context() as session:
            message_index = await get_next_message_index(session, conv.id)
            user_content = {"text": input_messages[-1].content}
            await save_message(
                session,
                conv.id,
                MessageRole.USER,
                user_content,
                message_index,
            )
            await session.commit()

        # Generate response (with conversation history)
        llm_messages = _convert_input_messages(messages_with_history)
        response = await generate_response(
            llm_messages,
            stream=False,
            model=request.model,
            temperature=request.temperature,
        )
        # Extract text from OpenResponses format
        response_text = response.output[0].content[0].text

        # Save assistant message
        async with get_db_context() as session:
            message_index = await get_next_message_index(session, conv.id)
            assistant_content = {"text": response_text}
            await save_message(
                session,
                conv.id,
                MessageRole.ASSISTANT,
                assistant_content,
                message_index,
            )
            await session.commit()

        # Mark complete
        async with get_db_context() as session:
            final_output = [{"role": "assistant", "content": response_text}]
            await update_response_status(
                session,
                response_id,
                ResponseStatus.COMPLETED,
                final_output=final_output,
            )
            await session.commit()

        return ResponsesResponse(
            id=response_id,
            output=[OutputItem(role="assistant", content=response_text)],
            conversation_id=str(conv.id)
        )


@responses_router.get("/responses/{response_id}")
async def get_response(response_id: str, stream: bool = False):
    """
    GET /responses/{id} - Resume streaming or retrieve completed response.

    Supports reconnecting to in-progress streams or fetching completed results.
    """
    async with get_db_context() as session:
        response_record = await get_response_record(session, response_id)
        await session.commit()

    if not response_record:
        raise HTTPException(status_code=404, detail="Response not found")

    # Status is stored as string in DB, normalize for comparison
    status_str = response_record.status if isinstance(response_record.status, str) else response_record.status.value

    if stream:
        # Resume streaming from current progress
        if status_str == ResponseStatus.COMPLETED.value:
            # Already completed, stream the final output
            async def stream_completed():
                if response_record.final_output:
                    for item in response_record.final_output:
                        content = item.get("content", "")
                        # Stream the content character by character or in chunks
                        for char in content:
                            event = {
                                "type": "response.output_text.delta",
                                "delta": char,
                            }
                            yield f"data: {json.dumps(event)}\n\n"

                done_event = {"type": "response.output_item.done"}
                yield f"data: {json.dumps(done_event)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(stream_completed(), media_type="text/event-stream")

        elif status_str == ResponseStatus.FAILED.value:
            raise HTTPException(status_code=500, detail=response_record.error_message)

        else:
            # Still in progress - would need conversation context to resume
            raise HTTPException(
                status_code=400,
                detail="Cannot resume in-progress streaming without original context",
            )

    else:
        # Return current state
        output = None
        if response_record.final_output:
            output = [
                OutputItem(role=item["role"], content=item["content"])
                for item in response_record.final_output
            ]

        return RetrieveResponseResponse(
            id=response_id,
            status=status_str,
            output=output,
            current_progress=response_record.current_progress,
            error_message=response_record.error_message,
        )
