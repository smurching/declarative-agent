"""Create estore-compatible schema

Revision ID: 001
Revises:
Create Date: 2026-02-16 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('internal_workspace_id', sa.Integer(), nullable=False),
        sa.Column('internal_last_updated_timestamp', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_timestamp', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_created', 'conversations', ['created_timestamp'], unique=False)
    op.create_index('idx_user_workspace', 'conversations', ['user_id', 'internal_workspace_id'], unique=False)

    # Create message_role enum (using SQLAlchemy, not raw SQL to avoid duplication)
    message_role_enum = postgresql.ENUM('USER', 'ASSISTANT', name='message_role', create_type=True)
    message_role_enum.create(op.get_bind(), checkfirst=True)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM('USER', 'ASSISTANT', name='message_role', create_type=False), nullable=False),
        sa.Column('created_timestamp', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('message_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('rating', sa.String(length=24), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'message_index', name='message_index_unique')
    )
    op.create_index('idx_conversation_messages', 'messages', ['conversation_id', 'message_index'], unique=False)

    # Create response_status enum (using SQLAlchemy, not raw SQL to avoid duplication)
    response_status_enum = postgresql.ENUM('in_progress', 'completed', 'failed', name='response_status', create_type=True)
    response_status_enum.create(op.get_bind(), checkfirst=True)

    # Create responses table
    op.create_table(
        'responses',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('in_progress', 'completed', 'failed', name='response_status', create_type=False), server_default=sa.text("'in_progress'"), nullable=False),
        sa.Column('background', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_timestamp', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_timestamp', sa.TIMESTAMP(), nullable=True),
        sa.Column('current_progress', sa.Text(), nullable=True),
        sa.Column('final_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conversation_responses', 'responses', ['conversation_id', 'created_timestamp'], unique=False)
    op.create_index('idx_status', 'responses', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_status', table_name='responses')
    op.drop_index('idx_conversation_responses', table_name='responses')
    op.drop_table('responses')
    postgresql.ENUM(name='response_status').drop(op.get_bind(), checkfirst=True)

    op.drop_index('idx_conversation_messages', table_name='messages')
    op.drop_table('messages')
    postgresql.ENUM(name='message_role').drop(op.get_bind(), checkfirst=True)

    op.drop_index('idx_user_workspace', table_name='conversations')
    op.drop_index('idx_created', table_name='conversations')
    op.drop_table('conversations')
