"""Agent runner - executes declarative agents using OpenResponses API."""

from typing import AsyncGenerator, Optional, Dict, Any, List, Union
from openai import AsyncOpenAI
import asyncio
import json
import httpx
import logging
import os

from .agent import DeclarativeAgent

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Runs declarative agents using the OpenResponses API backend.

    Supports streaming, non-streaming, and background execution modes.
    """

    def __init__(self, agent: DeclarativeAgent, user_id: int, workspace_profile: Optional[str] = None):
        """
        Initialize runner.

        Args:
            agent: Declarative agent to run
            user_id: User ID for backend requests
            workspace_profile: Optional Databricks workspace profile for authentication
                             (required for Databricks Apps URLs)
        """
        self.agent = agent
        self.user_id = user_id

        # Check if this is a Databricks Apps URL (requires special auth)
        is_databricks_app = "databricksapps.com" in agent.backend_url.lower()

        if is_databricks_app:
            # Use DatabricksOpenAI for Databricks Apps authentication
            try:
                from databricks_openai import AsyncDatabricksOpenAI
                from databricks.sdk import WorkspaceClient

                w = WorkspaceClient(profile=workspace_profile) if workspace_profile else WorkspaceClient()
                self.client = AsyncDatabricksOpenAI(
                    base_url=agent.backend_url,
                    workspace_client=w
                )
            except ImportError:
                raise ImportError(
                    "databricks-openai and databricks-sdk are required for Databricks Apps. "
                    "Install with: pip install databricks-openai databricks-sdk"
                )
        else:
            # Use standard OpenAI client for local/non-Databricks backends
            self.client = AsyncOpenAI(
                base_url=f"{agent.backend_url}/v1",
                api_key="not-needed",  # Backend doesn't require API key for local testing
            )

    def _prepare_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Prepare messages including system instructions if defined."""
        messages = []

        # Add system message if instructions are defined
        system_msg = self.agent.get_system_message()
        if system_msg:
            messages.append(system_msg)

        # Add user message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def run(
        self,
        message: str,
        stream: bool = False,
        background: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Run the agent with a user message.

        Args:
            message: User message to send to agent
            stream: Whether to stream the response
            background: Whether to run in background mode
            conversation_id: Optional conversation ID to continue existing conversation

        Returns:
            Response object (non-streaming/background) or async generator (streaming)
        """
        messages = self._prepare_messages(message)

        # Prepare databricks_options
        databricks_options = {"user_id": self.user_id}
        if conversation_id:
            databricks_options["conversation_id"] = conversation_id

        if background:
            # Background mode - returns immediately
            response = await self.client.responses.create(
                input=messages,
                model=self.agent.config.model,
                temperature=self.agent.config.temperature,
                background=True,
                extra_body={"databricks_options": databricks_options},
            )
            return {
                "id": response.id,
                "status": response.status,
                "conversation_id": getattr(response, "conversation_id", None),
            }

        elif stream:
            # Streaming mode - returns async generator
            stream_response = await self.client.responses.create(
                input=messages,
                model=self.agent.config.model,
                temperature=self.agent.config.temperature,
                stream=True,
                extra_body={"databricks_options": databricks_options},
            )
            return self._stream_events(stream_response)

        else:
            # Non-streaming mode - waits for complete response
            response = await self.client.responses.create(
                input=messages,
                model=self.agent.config.model,
                temperature=self.agent.config.temperature,
                stream=False,
                extra_body={"databricks_options": databricks_options},
            )
            return {
                "id": response.id,
                "output": [{"role": item.role, "content": item.content} for item in response.output],
                "status": getattr(response, "status", "completed"),
                "conversation_id": getattr(response, "conversation_id", None),
            }

    async def run_streaming(
        self,
        message: str,
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run agent in streaming mode, yielding SSE events.

        This method makes a direct HTTP call to the backend /v1/responses endpoint
        and yields SSE events as they arrive. Used by agent apps to proxy streaming
        to clients.

        Args:
            message: User message to send to agent
            conversation_id: Optional conversation ID to continue existing conversation

        Yields:
            SSE events from backend in OpenResponses format:
            - {"type": "response.output_text.delta", "delta": "..."}
            - {"type": "response.output_item.done", "item": {...}}

        Example:
            async for event in runner.run_streaming("What is 2+2?"):
                print(f"Event: {event}")
        """
        messages = self._prepare_messages(message)

        # Prepare request body
        request = {
            "input": messages,
            "stream": True,
            "databricks_options": {
                "user_id": self.user_id,
            },
            "model": self.agent.config.model,
            "temperature": self.agent.config.temperature,
        }

        if conversation_id:
            request["databricks_options"]["conversation_id"] = conversation_id

        # Make streaming HTTP request to backend
        url = f"{self.agent.backend_url}/v1/responses"

        # Get authentication headers if in Databricks Apps context
        headers = {}
        if os.getenv("DATABRICKS_HOST"):
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                # Trigger auth and get token from credentials provider
                credentials = w.config.authenticate()
                if credentials and hasattr(credentials, 'token'):
                    token = credentials.token()
                    headers["Authorization"] = f"Bearer {token}"
                    logger.debug("Added Databricks auth header for backend request")
                else:
                    logger.warning("Could not extract token from credentials")
            except Exception as e:
                logger.warning(f"Could not get Databricks auth token: {e}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream("POST", url, json=request, headers=headers) as response:
                    response.raise_for_status()

                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            if data == "[DONE]":
                                break

                            try:
                                event = json.loads(data)
                                yield event
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE event: {data}")
                                continue

            except httpx.HTTPStatusError as e:
                logger.error(f"Backend returned error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error in streaming request: {e}")
                raise

    async def _stream_events(self, stream) -> AsyncGenerator[Dict[str, Any], None]:
        """Process streaming events from the backend."""
        async for event in stream:
            # Convert SDK event to dict
            if hasattr(event, "delta"):
                yield {"type": "delta", "delta": event.delta}
            elif hasattr(event, "type"):
                yield {"type": event.type}
            else:
                yield {"type": "event", "data": str(event)}

    async def retrieve(self, response_id: str, stream: bool = False):
        """
        Retrieve a response (useful for background tasks).

        Args:
            response_id: Response ID to retrieve
            stream: Whether to stream the retrieval

        Returns:
            Response object or async generator (if streaming)
        """
        if stream:
            # Resume streaming from where it left off
            stream_response = await self.client.responses.retrieve(
                response_id, stream=True
            )
            return self._stream_events(stream_response)
        else:
            # Get completed response
            response = await self.client.responses.retrieve(response_id)
            return {
                "id": response.id,
                "status": response.status,
                "output": [{"role": item.role, "content": item.content} for item in response.output] if response.output else None,
            }

    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
