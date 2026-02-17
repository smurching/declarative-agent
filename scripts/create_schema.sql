-- Create schema and tables for agent_backend in PostgreSQL
CREATE SCHEMA IF NOT EXISTS agent_backend;

-- Create conversations table
CREATE TABLE IF NOT EXISTS agent_backend.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_workspace_id BIGINT NOT NULL,
    internal_last_updated_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id BIGINT NOT NULL,
    created_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_workspace ON agent_backend.conversations(user_id, internal_workspace_id);
CREATE INDEX IF NOT EXISTS idx_created ON agent_backend.conversations(created_timestamp);

-- Create messages table
CREATE TABLE IF NOT EXISTS agent_backend.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES agent_backend.conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    created_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    message_index INTEGER NOT NULL,
    content BYTEA NOT NULL,
    rating VARCHAR(24),
    CONSTRAINT message_index_unique UNIQUE (conversation_id, message_index)
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages ON agent_backend.messages(conversation_id, message_index);

-- Create responses table
CREATE TABLE IF NOT EXISTS agent_backend.responses (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES agent_backend.conversations(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    background BOOLEAN NOT NULL DEFAULT false,
    created_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_timestamp TIMESTAMP WITHOUT TIME ZONE,
    current_progress TEXT,
    final_output JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversation_responses ON agent_backend.responses(conversation_id, created_timestamp);
CREATE INDEX IF NOT EXISTS idx_status ON agent_backend.responses(status);
