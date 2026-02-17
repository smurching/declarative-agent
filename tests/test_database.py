"""
Database layer tests.

Tests for database models, queries, and data integrity.
"""
import pytest
from uuid import uuid4
from datetime import datetime
import json


class TestConversationModel:
    """Tests for the Conversation model."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session, sample_user_id, sample_workspace_id):
        """Test creating a conversation."""
        from server.db.queries import create_conversation

        conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        assert conv.id is not None
        assert conv.user_id == sample_user_id
        assert conv.internal_workspace_id == sample_workspace_id
        assert conv.created_timestamp is not None

    @pytest.mark.asyncio
    async def test_get_conversation(self, db_session, existing_conversation):
        """Test retrieving a conversation by ID."""
        from server.db.queries import get_conversation

        conv = await get_conversation(db_session, existing_conversation.id)
        assert conv is not None
        assert conv.id == existing_conversation.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, db_session):
        """Test retrieving a non-existent conversation returns None."""
        from server.db.queries import get_conversation

        fake_id = uuid4()
        conv = await get_conversation(db_session, fake_id)
        assert conv is None


class TestMessageModel:
    """Tests for the Message model."""

    @pytest.mark.asyncio
    async def test_save_message(self, db_session, existing_conversation):
        """Test saving a message."""
        from server.db.queries import save_message
        from server.db.models import MessageRole

        content = {"text": "Test message"}
        msg = await save_message(
            db_session,
            existing_conversation.id,
            MessageRole.USER,
            content,
            10
        )
        await db_session.commit()

        assert msg.id is not None
        assert msg.conversation_id == existing_conversation.id
        assert msg.role == MessageRole.USER
        assert msg.message_index == 10

    @pytest.mark.asyncio
    async def test_message_content_json_serialization(self, db_session, existing_conversation):
        """Test that message content is properly JSON serialized."""
        from server.db.queries import save_message, get_messages
        from server.db.models import MessageRole

        content = {
            "text": "Complex message",
            "metadata": {
                "timestamp": "2024-01-01",
                "tags": ["test", "demo"]
            }
        }

        await save_message(
            db_session,
            existing_conversation.id,
            MessageRole.ASSISTANT,
            content,
            20
        )
        await db_session.commit()

        # Retrieve and deserialize
        messages = await get_messages(db_session, existing_conversation.id)
        saved_msg = next(m for m in messages if m.message_index == 20)

        saved_content = json.loads(saved_msg.content.decode("utf-8"))
        assert saved_content == content

    @pytest.mark.asyncio
    async def test_get_messages_ordering(self, db_session, existing_conversation):
        """Test that messages are returned in message_index order."""
        from server.db.queries import get_messages

        messages = await get_messages(db_session, existing_conversation.id)

        # Check ordering
        indices = [m.message_index for m in messages]
        assert indices == sorted(indices)

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, db_session, existing_conversation):
        """Test message pagination."""
        from server.db.queries import get_messages

        # Get first 2 messages
        messages = await get_messages(db_session, existing_conversation.id, limit=2, offset=0)
        assert len(messages) <= 2

        # Get next message
        messages_page2 = await get_messages(db_session, existing_conversation.id, limit=1, offset=2)
        if messages_page2:
            # Should be after the first 2
            assert messages_page2[0].message_index >= 2

    @pytest.mark.asyncio
    async def test_get_next_message_index(self, db_session, existing_conversation):
        """Test getting the next message index."""
        from server.db.queries import get_next_message_index, get_messages

        # Get current messages
        messages = await get_messages(db_session, existing_conversation.id)
        current_max = max(m.message_index for m in messages)

        # Get next index
        next_index = await get_next_message_index(db_session, existing_conversation.id)

        assert next_index == current_max + 1

    @pytest.mark.asyncio
    async def test_get_next_message_index_empty_conversation(self, db_session, sample_user_id, sample_workspace_id):
        """Test getting next message index for a conversation with no messages."""
        from server.db.queries import create_conversation, get_next_message_index

        conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        next_index = await get_next_message_index(db_session, conv.id)
        assert next_index == 0


class TestResponseModel:
    """Tests for the Response model."""

    @pytest.mark.asyncio
    async def test_create_response_record(self, db_session, existing_conversation):
        """Test creating a response record."""
        from server.db.queries import create_response_record

        response_id = "resp_test123"
        response = await create_response_record(
            db_session,
            response_id,
            existing_conversation.id,
            background=False
        )
        await db_session.commit()

        assert response.id == response_id
        assert response.conversation_id == existing_conversation.id
        assert response.background is False
        assert response.status.value == "in_progress"

    @pytest.mark.asyncio
    async def test_get_response_record(self, db_session, existing_conversation):
        """Test retrieving a response record."""
        from server.db.queries import create_response_record, get_response_record

        response_id = "resp_test456"
        await create_response_record(
            db_session,
            response_id,
            existing_conversation.id
        )
        await db_session.commit()

        # Retrieve it
        response = await get_response_record(db_session, response_id)
        assert response is not None
        assert response.id == response_id

    @pytest.mark.asyncio
    async def test_update_response_progress(self, db_session, existing_conversation):
        """Test updating response progress."""
        from server.db.queries import (
            create_response_record,
            update_response_progress,
            get_response_record
        )

        response_id = "resp_progress_test"
        await create_response_record(
            db_session,
            response_id,
            existing_conversation.id
        )
        await db_session.commit()

        # Update progress
        progress_text = "Partial response..."
        await update_response_progress(db_session, response_id, progress_text)
        await db_session.commit()

        # Verify
        response = await get_response_record(db_session, response_id)
        assert response.current_progress == progress_text

    @pytest.mark.asyncio
    async def test_update_response_status_completed(self, db_session, existing_conversation):
        """Test updating response status to completed."""
        from server.db.queries import (
            create_response_record,
            update_response_status,
            get_response_record
        )
        from server.db.models import ResponseStatus

        response_id = "resp_completed_test"
        await create_response_record(
            db_session,
            response_id,
            existing_conversation.id
        )
        await db_session.commit()

        # Update to completed
        final_output = [{"role": "assistant", "content": "Final answer"}]
        await update_response_status(
            db_session,
            response_id,
            ResponseStatus.COMPLETED,
            final_output=final_output
        )
        await db_session.commit()

        # Verify
        response = await get_response_record(db_session, response_id)
        assert response.status == ResponseStatus.COMPLETED
        assert response.final_output == final_output
        assert response.completed_timestamp is not None

    @pytest.mark.asyncio
    async def test_update_response_status_failed(self, db_session, existing_conversation):
        """Test updating response status to failed."""
        from server.db.queries import (
            create_response_record,
            update_response_status,
            get_response_record
        )
        from server.db.models import ResponseStatus

        response_id = "resp_failed_test"
        await create_response_record(
            db_session,
            response_id,
            existing_conversation.id
        )
        await db_session.commit()

        # Update to failed
        error_msg = "Something went wrong"
        await update_response_status(
            db_session,
            response_id,
            ResponseStatus.FAILED,
            error_message=error_msg
        )
        await db_session.commit()

        # Verify
        response = await get_response_record(db_session, response_id)
        assert response.status == ResponseStatus.FAILED
        assert response.error_message == error_msg


class TestCascadeDeletes:
    """Tests for cascade delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_conversation_deletes_messages(
        self, db_session, sample_user_id, sample_workspace_id
    ):
        """Test that deleting a conversation deletes its messages."""
        from server.db.queries import create_conversation, save_message, get_messages
        from server.db.models import MessageRole

        # Create conversation with messages
        conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        await save_message(db_session, conv.id, MessageRole.USER, {"text": "Test"}, 0)
        await db_session.commit()

        # Verify message exists
        messages = await get_messages(db_session, conv.id)
        assert len(messages) == 1

        # Delete conversation
        await db_session.delete(conv)
        await db_session.commit()

        # Messages should be deleted too (cascade)
        messages = await get_messages(db_session, conv.id)
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_delete_conversation_deletes_responses(
        self, db_session, sample_user_id, sample_workspace_id
    ):
        """Test that deleting a conversation deletes its responses."""
        from server.db.queries import create_conversation, create_response_record, get_response_record

        # Create conversation with response
        conv = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        response_id = "resp_cascade_test"
        await create_response_record(db_session, response_id, conv.id)
        await db_session.commit()

        # Verify response exists
        response = await get_response_record(db_session, response_id)
        assert response is not None

        # Delete conversation
        await db_session.delete(conv)
        await db_session.commit()

        # Response should be deleted too (cascade)
        response = await get_response_record(db_session, response_id)
        assert response is None


class TestDataIntegrity:
    """Tests for data integrity constraints."""

    @pytest.mark.asyncio
    async def test_message_requires_conversation(self, db_session):
        """Test that message requires valid conversation_id."""
        from server.db.models import Message, MessageRole
        from sqlalchemy.exc import IntegrityError

        # Try to create message with non-existent conversation
        fake_conv_id = uuid4()
        msg = Message(
            conversation_id=fake_conv_id,
            role=MessageRole.USER,
            message_index=0,
            content=b'{"text": "test"}'
        )
        db_session.add(msg)

        # Should fail foreign key constraint
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_message_index_unique_per_conversation(
        self, db_session, existing_conversation, sample_user_id, sample_workspace_id
    ):
        """Test that message_index is unique per conversation."""
        from server.db.queries import save_message, create_conversation
        from server.db.models import MessageRole
        from sqlalchemy.exc import IntegrityError

        # Create two different conversations
        conv2 = await create_conversation(db_session, sample_user_id, sample_workspace_id)
        await db_session.commit()

        # Same index in different conversations should be OK
        await save_message(db_session, existing_conversation.id, MessageRole.USER, {"text": "C1"}, 50)
        await save_message(db_session, conv2.id, MessageRole.USER, {"text": "C2"}, 50)
        await db_session.commit()

        # But same index in same conversation should fail
        with pytest.raises(IntegrityError):
            await save_message(db_session, existing_conversation.id, MessageRole.USER, {"text": "Duplicate"}, 50)
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_conversation_requires_user_and_workspace(self, db_session):
        """Test that conversation requires user_id and workspace_id."""
        from server.db.models import Conversation
        from sqlalchemy.exc import IntegrityError

        # Try to create conversation without required fields
        conv = Conversation()
        db_session.add(conv)

        with pytest.raises(IntegrityError):
            await db_session.commit()
