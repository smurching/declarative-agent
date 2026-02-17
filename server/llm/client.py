"""LLM client for Databricks."""
from databricks_openai import AsyncDatabricksOpenAI
from functools import lru_cache
from typing import AsyncIterator, List, Dict
import logging

from server.config import get_settings
from server.auth.databricks import get_workspace_client

logger = logging.getLogger(__name__)


@lru_cache
def get_llm_client() -> AsyncDatabricksOpenAI:
    """
    Get OpenAI client configured for Databricks.

    Automatically authenticates via Databricks SDK.
    Returns cached instance for reuse.
    """
    # Use the workspace client with dogfood profile
    workspace_client = get_workspace_client()
    return AsyncDatabricksOpenAI(workspace_client=workspace_client)


async def generate_response(
    messages: List[Dict[str, str]],
    stream: bool = False,
    model: str = None,
    temperature: float = 0.7,
):
    """
    Call Databricks LLM endpoint using Responses API.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        stream: Whether to stream the response
        model: Model name (defaults to configured endpoint)
        temperature: Sampling temperature

    Returns:
        Response object or AsyncIterator of chunks (via responses.create)
    """
    client = get_llm_client()
    settings = get_settings()

    if model is None:
        model = settings.databricks_serving_endpoint

    logger.info(f"Calling LLM with model={model}, stream={stream}, messages={len(messages)}")

    # Use responses.create() instead of chat.completions.create()
    # This aligns with the OpenResponses API pattern
    response = await client.responses.create(
        model=model,
        input=messages,  # responses API uses 'input' instead of 'messages'
        stream=stream,
        temperature=temperature,
    )

    return response


async def stream_llm_response(
    messages: List[Dict[str, str]],
    model: str = None,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """
    Stream LLM response chunks using Responses API.

    Args:
        messages: List of message dictionaries
        model: Model name
        temperature: Sampling temperature

    Yields:
        Text chunks from the LLM
    """
    response = await generate_response(
        messages=messages,
        stream=True,
        model=model,
        temperature=temperature,
    )

    async for event in response:
        # Handle responses API streaming format
        # Events have a 'type' field and may contain delta or other content
        if hasattr(event, 'type'):
            event_type = event.type
            # Extract text from delta events
            if 'delta' in event_type:
                if hasattr(event, 'delta'):
                    yield event.delta
                elif hasattr(event, 'content'):
                    # Some events may have content field directly
                    for content_item in event.content:
                        if hasattr(content_item, 'text'):
                            yield content_item.text
        # Fallback: handle chat completions format if responses API not available
        elif hasattr(event, 'choices') and len(event.choices) > 0:
            delta = event.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                yield delta.content
