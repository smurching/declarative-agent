"""OpenResponses API type definitions."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
from uuid import UUID


class InputMessage(BaseModel):
    """Input message for /responses endpoint."""

    role: Literal["user", "assistant", "system"]
    content: str


class DatabricksOptions(BaseModel):
    """Databricks-specific options."""

    conversation_id: Optional[UUID] = None
    user_id: int = 0  # Default for testing


class ResponsesRequest(BaseModel):
    """
    Request body for POST /v1/responses.

    OpenAI-compatible with optional Databricks extensions.
    """

    # OpenAI standard parameters
    input: Union[str, List[InputMessage]]  # Can be string or message list
    model: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_output_tokens: Optional[int] = None

    # Databricks extensions
    background: bool = False
    databricks_options: Optional[DatabricksOptions] = None

    # Conversation context (OpenAI style)
    conversation: Optional[Dict[str, Any]] = None


class OutputItem(BaseModel):
    """Output item in response."""

    role: Literal["assistant"]
    content: str


class ResponsesResponse(BaseModel):
    """Non-streaming response from /responses."""

    id: str
    output: List[OutputItem]
    status: Optional[str] = "completed"
    conversation_id: Optional[str] = None  # For tracking conversations in tests


class BackgroundResponse(BaseModel):
    """Response for background mode."""

    id: str
    status: Literal["in_progress"]
    conversation_id: Optional[str] = None  # For tracking conversations in tests


class StreamEvent(BaseModel):
    """SSE event for streaming responses."""

    type: str
    delta: Optional[Dict[str, Any]] = None
    item: Optional[Dict[str, Any]] = None


class RetrieveResponseResponse(BaseModel):
    """Response for GET /responses/{id}."""

    id: str
    status: str
    output: Optional[List[OutputItem]] = None
    current_progress: Optional[str] = None
    error_message: Optional[str] = None
