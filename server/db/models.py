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
import enum
import uuid as uuid_module
import json
import os

Base = declarative_base()

# Use a custom schema that the service principal owns (PostgreSQL only)
SCHEMA_NAME = "agent_backend"


def get_db_type():
    """Get current database type from environment."""
    return os.getenv("DB_TYPE", "postgres").lower()


def table_args_with_schema(*args):
    """
    Create __table_args__ tuple with conditional schema.

    For PostgreSQL: Includes schema in the dict.
    For SQLite: Omits schema (not supported).
    """
    db_type = get_db_type()
    if db_type == "postgres":
        return args + ({"schema": SCHEMA_NAME},)
    else:
        return args + ({},)


def enum_column(enum_class, name, **kwargs):
    """
    Create an Enum column that works across databases.

    For PostgreSQL: Uses native ENUM type with schema.
    For SQLite: Uses String column with validation.
    """
    db_type = get_db_type()
    if db_type == "postgres":
        return Column(
            SQLEnum(enum_class, name=name, schema=SCHEMA_NAME, values_callable=lambda x: [e.value for e in x]),
            **kwargs
        )
    else:
        # SQLite: use String with check constraint
        return Column(String(50), **kwargs)


def fk_reference(table_name, column="id", **kwargs):
    """
    Create a ForeignKey reference that works across databases.

    For PostgreSQL: Includes schema prefix.
    For SQLite: No schema prefix.
    """
    db_type = get_db_type()
    if db_type == "postgres":
        return ForeignKey(f"{SCHEMA_NAME}.{table_name}.{column}", **kwargs)
    else:
        return ForeignKey(f"{table_name}.{column}", **kwargs)


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

    __table_args__ = table_args_with_schema(
        Index("idx_user_workspace", "user_id", "internal_workspace_id"),
        Index("idx_created", "created_timestamp"),
    )


class Message(Base):
    """
    Messages table (estore-compatible).

    Stores individual messages within conversations with ordering via message_index.
    """

    __tablename__ = "messages"

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    conversation_id = Column(
        UUID(),
        fk_reference("conversations", ondelete="CASCADE"),
        nullable=False,
    )
    role = enum_column(MessageRole, 'message_role', nullable=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    message_index = Column(Integer, nullable=False)
    content = Column(LargeBinary, nullable=False)  # JSON serialized as bytes
    rating = Column(String(24), nullable=True)  # Optional user feedback

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = table_args_with_schema(
        UniqueConstraint("conversation_id", "message_index", name="message_index_unique"),
        Index("idx_conversation_messages", "conversation_id", "message_index"),
    )


class Response(Base):
    """
    Responses table for background mode and resumption.

    Tracks response execution state for streaming resumption and background tasks.
    """

    __tablename__ = "responses"

    id = Column(String(64), primary_key=True)  # resp_abc123
    conversation_id = Column(
        UUID(),
        fk_reference("conversations", ondelete="CASCADE"),
        nullable=False,
    )
    status = enum_column(ResponseStatus, 'response_status', nullable=False, default=ResponseStatus.IN_PROGRESS)
    background = Column(Boolean, nullable=False, default=False)
    created_timestamp = Column(TIMESTAMP(), server_default=func.now())
    completed_timestamp = Column(TIMESTAMP(), nullable=True)
    current_progress = Column(Text, nullable=True)  # Partial output for resumption
    final_output = Column(JSON(), nullable=True)  # Completed output
    error_message = Column(Text, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="responses")

    __table_args__ = table_args_with_schema(
        Index("idx_conversation_responses", "conversation_id", "created_timestamp"),
        Index("idx_status", "status"),
    )
