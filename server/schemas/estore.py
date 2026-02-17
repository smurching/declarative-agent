"""Estore-compatible type definitions."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class MessageRoleEnum(str, Enum):
    """Message role enumeration."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ConversationResponse(BaseModel):
    """Conversation response model."""

    id: UUID
    user_id: int
    internal_workspace_id: int
    created_timestamp: datetime
    internal_last_updated_timestamp: datetime

    class Config:
        from_attributes = True


class MessageContent(BaseModel):
    """Message content structure."""

    text: str
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    """Message response model."""

    id: UUID
    conversation_id: UUID
    role: MessageRoleEnum
    message_index: int
    content: MessageContent
    rating: Optional[str] = None
    created_timestamp: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(BaseModel):
    """Conversation with messages."""

    conversation: ConversationResponse
    messages: List[MessageResponse]
