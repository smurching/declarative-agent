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
    Call Databricks LLM endpoint using OpenResponses API.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        stream: Whether to stream the response
        model: Model name (defaults to configured endpoint)
        temperature: Sampling temperature

    Returns:
        Response object or AsyncIterator of response chunks
    """
    client = get_llm_client()
    settings = get_settings()

    if model is None:
        model = settings.databricks_serving_endpoint

    logger.info(f"Calling LLM with model={model}, stream={stream}, messages={len(messages)}")

    # Use responses.create - OpenResponses API supported by Databricks model serving
    response = await client.responses.create(
        model=model,
        input=messages,  # OpenResponses uses 'input' not 'messages'
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
    Stream LLM response chunks.

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

    async for chunk in response:
        # Handle OpenResponses streaming format
        if hasattr(chunk, 'type') and chunk.type == 'response.output_text.delta':
            # Response delta events have text directly
            if hasattr(chunk, 'delta') and chunk.delta:
                yield chunk.delta
