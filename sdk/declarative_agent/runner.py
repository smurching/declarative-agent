"""Agent runner - executes declarative agents using OpenResponses API."""

from typing import AsyncGenerator, Optional, Dict, Any, List, Union
from openai import AsyncOpenAI
import asyncio

from .agent import DeclarativeAgent


class AgentRunner:
    """
    Runs declarative agents using the OpenResponses API backend.

    Supports streaming, non-streaming, and background execution modes.
    """

    def __init__(self, agent: DeclarativeAgent, user_id: int):
        """
        Initialize runner.

        Args:
            agent: Declarative agent to run
            user_id: User ID for backend requests
        """
        self.agent = agent
        self.user_id = user_id

        # Initialize OpenAI client pointing to our backend
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
                "output": response.output if response.output else None,
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
