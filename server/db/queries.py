"""Database CRUD operations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import json
from typing import Optional, List
from datetime import datetime

from server.db.models import Conversation, Message, Response, MessageRole, ResponseStatus


async def create_conversation(
    session: AsyncSession, user_id: int, workspace_id: int
) -> Conversation:
    """
    Create a new conversation.

    Args:
        session: Database session
        user_id: User ID
        workspace_id: Workspace ID

    Returns:
        Created conversation object
    """
    conv = Conversation(
        user_id=user_id,
        internal_workspace_id=workspace_id,
    )
    session.add(conv)
    await session.flush()
    await session.refresh(conv)
    return conv


async def get_conversation(session: AsyncSession, conversation_id: UUID) -> Optional[Conversation]:
    """
    Retrieve a conversation by ID.

    Args:
        session: Database session
        conversation_id: Conversation UUID

    Returns:
        Conversation object or None if not found
    """
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return result.scalar_one_or_none()


async def get_next_message_index(session: AsyncSession, conversation_id: UUID) -> int:
    """
    Get the next message index for a conversation.

    Args:
        session: Database session
        conversation_id: Conversation UUID

    Returns:
        Next available message index
    """
    result = await session.execute(
        select(func.max(Message.message_index))
        .where(Message.conversation_id == conversation_id)
    )
    max_index = result.scalar()
    return (max_index + 1) if max_index is not None else 0


async def save_message(
    session: AsyncSession,
    conversation_id: UUID,
    role: MessageRole,
    content: dict,
    message_index: int,
) -> Message:
    """
    Save a message to the database.

    Args:
        session: Database session
        conversation_id: Conversation UUID
        role: Message role (USER or ASSISTANT)
        content: Message content as dictionary
        message_index: Message ordering index

    Returns:
        Created message object
    """
    content_bytes = json.dumps(content).encode("utf-8")
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content_bytes,
        message_index=message_index,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    return msg


async def get_messages(
    session: AsyncSession,
    conversation_id: UUID,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Message]:
    """
    Retrieve messages for a conversation.

    Args:
        session: Database session
        conversation_id: Conversation UUID
        limit: Maximum number of messages to return
        offset: Number of messages to skip

    Returns:
        List of message objects ordered by message_index
    """
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.message_index)
        .offset(offset)
    )

    if limit:
        query = query.limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def create_response_record(
    session: AsyncSession,
    response_id: str,
    conversation_id: UUID,
    background: bool = False,
) -> Response:
    """
    Create a response record for tracking.

    Args:
        session: Database session
        response_id: Response ID (resp_abc123)
        conversation_id: Conversation UUID
        background: Whether this is a background task

    Returns:
        Created response object
    """
    response = Response(
        id=response_id,
        conversation_id=conversation_id,
        background=background,
        status=ResponseStatus.IN_PROGRESS,
    )
    session.add(response)
    await session.flush()
    await session.refresh(response)
    return response


async def get_response_record(session: AsyncSession, response_id: str) -> Optional[Response]:
    """
    Retrieve a response record by ID.

    Args:
        session: Database session
        response_id: Response ID

    Returns:
        Response object or None if not found
    """
    result = await session.execute(
        select(Response).where(Response.id == response_id)
    )
    return result.scalar_one_or_none()


async def update_response_progress(
    session: AsyncSession,
    response_id: str,
    progress: str,
) -> None:
    """
    Update response progress (for resumption).

    Args:
        session: Database session
        response_id: Response ID
        progress: Current progress text
    """
    result = await session.execute(
        select(Response).where(Response.id == response_id)
    )
    response = result.scalar_one_or_none()

    if response:
        response.current_progress = progress
        await session.flush()


async def update_response_status(
    session: AsyncSession,
    response_id: str,
    status: ResponseStatus,
    final_output: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Update response status and final output.

    Args:
        session: Database session
        response_id: Response ID
        status: New status
        final_output: Final output data (if completed)
        error_message: Error message (if failed)
    """
    result = await session.execute(
        select(Response).where(Response.id == response_id)
    )
    response = result.scalar_one_or_none()

    if response:
        response.status = status

        if status == ResponseStatus.COMPLETED:
            response.completed_timestamp = datetime.utcnow()
            if final_output:
                response.final_output = final_output

        if status == ResponseStatus.FAILED and error_message:
            response.error_message = error_message

        await session.flush()
