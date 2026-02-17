"""SQLAlchemy models for estore-compatible schema."""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    LargeBinary,
    TIMESTAMP,
    Enum,
    ForeignKey,
    Boolean,
    Index,
    UniqueConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

# Use a custom schema that the service principal owns
SCHEMA_NAME = "agent_backend"


class MessageRole(str, enum.Enum):
    """Message role enumeration."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ResponseStatus(str, enum.Enum):
    """Response status enumeration."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Conversation(Base):
    """
    Conversations table (estore-compatible).

    Stores conversation metadata and links to messages.
    """

    __tablename__ = "conversations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    internal_workspace_id = Column(BigInteger, nullable=False)
    internal_last_updated_timestamp = Column(
        TIMESTAMP(), server_default=func.now(), onupdate=func.now()
    )
    user_id = Column(BigInteger, nullable=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_workspace", "user_id", "internal_workspace_id"),
        Index("idx_created", "created_timestamp"),
        {"schema": SCHEMA_NAME},
    )


class Message(Base):
    """
    Messages table (estore-compatible).

    Stores individual messages within conversations with ordering via message_index.
    """

    __tablename__ = "messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(Enum(MessageRole, name='message_role', schema=SCHEMA_NAME, values_callable=lambda x: [e.value for e in x]), nullable=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    message_index = Column(Integer, nullable=False)
    content = Column(LargeBinary, nullable=False)  # JSON serialized as bytes
    rating = Column(String(24), nullable=True)  # Optional user feedback

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        UniqueConstraint("conversation_id", "message_index", name="message_index_unique"),
        Index("idx_conversation_messages", "conversation_id", "message_index"),
        {"schema": SCHEMA_NAME},
    )


class Response(Base):
    """
    Responses table for background mode and resumption.

    Tracks response execution state for streaming resumption and background tasks.
    """

    __tablename__ = "responses"

    id = Column(String(64), primary_key=True)  # resp_abc123
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(
        Enum(ResponseStatus, name='response_status', schema=SCHEMA_NAME, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=text("'in_progress'"),
    )
    background = Column(Boolean, nullable=False, server_default=text("false"))
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    completed_timestamp = Column(TIMESTAMP(), nullable=True)
    current_progress = Column(Text, nullable=True)  # Partial output for resumption
    final_output = Column(JSONB, nullable=True)  # Completed output
    error_message = Column(Text, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="responses")

    __table_args__ = (
        Index("idx_conversation_responses", "conversation_id", "created_timestamp"),
        Index("idx_status", "status"),
        {"schema": SCHEMA_NAME},
    )
