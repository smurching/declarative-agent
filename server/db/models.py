"""SQLAlchemy models for estore-compatible schema with multi-database support."""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    LargeBinary,
    TIMESTAMP,
    Enum as SQLEnum,
    ForeignKey,
    Boolean,
    Index,
    UniqueConstraint,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func, text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import MetaData
import enum
import uuid as uuid_module
import json
import os

# Use a custom schema that the service principal owns (PostgreSQL only)
SCHEMA_NAME = "agent_backend"


def get_db_type():
    """Get current database type from environment."""
    return os.getenv("DB_TYPE", "postgres").lower()


def _is_postgres():
    """Check if we're using PostgreSQL (vs SQLite for testing)."""
    # If PGHOST is set, we're definitely using PostgreSQL
    if os.getenv("PGHOST"):
        return True
    # If DB_TYPE is explicitly set to postgres
    if os.getenv("DB_TYPE", "").lower() == "postgres":
        return True
    # Default to SQLite for local testing
    return False


# Create Base with schema already set for PostgreSQL
if _is_postgres():
    print(f"[MODELS] Creating Base with schema: {SCHEMA_NAME} (PGHOST={os.getenv('PGHOST', 'NOT SET')})")
    metadata = MetaData(schema=SCHEMA_NAME)
    Base = declarative_base(metadata=metadata)
else:
    print(f"[MODELS] Creating Base without schema (PGHOST={os.getenv('PGHOST', 'NOT SET')}, DB_TYPE={os.getenv('DB_TYPE', 'NOT SET')})")
    Base = declarative_base()


# Note: Schema is only used for PostgreSQL, SQLite ignores it
# Table args will need to be set dynamically or use a default that works for both
DEFAULT_TABLE_ARGS = {}  # Can be overridden at engine creation time


class UUID(TypeDecorator):
    """
    Platform-independent UUID type.

    Uses PostgreSQL UUID on PostgreSQL, String(36) on SQLite.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid_module.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            if isinstance(value, uuid_module.UUID):
                return value
            return value
        else:
            if isinstance(value, str):
                return uuid_module.UUID(value)
            return value


class JSON(TypeDecorator):
    """
    Platform-independent JSON type.

    Uses JSONB on PostgreSQL, Text on SQLite (with JSON serialization).
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB)
        else:
            return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name != 'postgresql':
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name != 'postgresql':
            return json.loads(value)
        return value


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
    __table_args__ = (
        Index("idx_user_workspace", "user_id", "internal_workspace_id"),
        Index("idx_created", "created_timestamp"),
    )

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    internal_workspace_id = Column(BigInteger, nullable=False)
    internal_last_updated_timestamp = Column(
        TIMESTAMP(), server_default=func.now(), onupdate=func.now()
    )
    user_id = Column(BigInteger, nullable=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """
    Messages table (estore-compatible).

    Stores individual messages within conversations with ordering via message_index.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "message_index", name="message_index_unique"),
        Index("idx_conversation_messages", "conversation_id", "message_index"),
    )

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    # FK will be set based on Base.metadata.schema (set at runtime in main.py)
    conversation_id = Column(UUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # Store enum as string
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    message_index = Column(Integer, nullable=False)
    content = Column(LargeBinary, nullable=False)  # JSON serialized as bytes
    rating = Column(String(24), nullable=True)  # Optional user feedback

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Response(Base):
    """
    Responses table for background mode and resumption.

    Tracks response execution state for streaming resumption and background tasks.
    """

    __tablename__ = "responses"
    __table_args__ = (
        Index("idx_conversation_responses", "conversation_id", "created_timestamp"),
        Index("idx_status", "status"),
    )

    id = Column(String(64), primary_key=True)  # resp_abc123
    # FK will be set based on Base.metadata.schema (set at runtime in main.py)
    conversation_id = Column(UUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="in_progress")  # Store enum as string
    background = Column(Boolean, nullable=False, default=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    completed_timestamp = Column(TIMESTAMP(), nullable=True)
    current_progress = Column(Text, nullable=True)  # Partial output for resumption
    final_output = Column(JSON(), nullable=True)  # Completed output
    error_message = Column(Text, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="responses")
