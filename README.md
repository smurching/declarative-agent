# Agent Backend with OpenResponses API

A prototype agent backend built on Databricks Apps + Lakebase, implementing an OpenResponses-compatible API for conversation management and LLM interaction.

## Features

- **OpenResponses-compatible /responses API** - Supports streaming, non-streaming, and background modes
- **Estore-compatible conversation schema** - Message ordering via `message_index`
- **Databricks LLM integration** - Via OpenAI SDK with automatic authentication
- **Lakebase (Postgres) persistence** - Async SQLAlchemy with connection pooling
- **FastAPI + uvicorn** - High-performance async web framework

## Architecture

```
POST /responses → Conversation Handler → Databricks LLM
                         ↓
                   Lakebase (Postgres)
```

## Prerequisites

- Python 3.12+
- uv (Python package manager)
- Databricks CLI configured with authentication
- Access to Databricks workspace with:
  - LLM serving endpoint (e.g., `databricks-gpt-5-2`)
  - Lakebase instance

## Quick Start

### 1. Install Dependencies

```bash
cd ~/agent-backend
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
# Edit .env with your Databricks workspace details
```

### 3. Run Database Migrations

```bash
python scripts/migrate.py
```

### 4. Run Locally

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### 5. Deploy to Databricks Apps

```bash
# Validate bundle configuration
databricks bundle validate

# Deploy the app
databricks bundle deploy

# Start the app
databricks bundle run agent_backend
```

## API Usage

### POST /responses (Streaming)

```bash
curl -X POST http://localhost:8000/responses \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": true,
    "databricks_options": {"user_id": 12345}
  }'
```

**Response (SSE):**
```
data: {"type": "response.output_item.delta", "delta": {"text": "Hi"}}
data: {"type": "response.output_item.done"}
data: [DONE]
```

### POST /responses (Non-streaming)

```bash
curl -X POST http://localhost:8000/responses \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "What is 2+2?"}],
    "stream": false,
    "databricks_options": {"user_id": 12345}
  }'
```

**Response:**
```json
{
  "id": "resp_abc123",
  "output": [
    {"role": "assistant", "content": "2+2 equals 4."}
  ]
}
```

### POST /responses (Background Mode)

```bash
curl -X POST http://localhost:8000/responses \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Long-running task"}],
    "background": true,
    "databricks_options": {"user_id": 12345}
  }'
```

**Response:**
```json
{
  "id": "resp_abc123",
  "status": "in_progress"
}
```

### GET /responses/{id} (Retrieve)

```bash
curl http://localhost:8000/responses/resp_abc123
```

**Response:**
```json
{
  "id": "resp_abc123",
  "status": "completed",
  "output": [
    {"role": "assistant", "content": "Task completed."}
  ]
}
```

### GET /health

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "ok",
  "llm": "ok"
}
```

## Database Schema

### Conversations Table

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    internal_workspace_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    created_timestamp TIMESTAMP(6),
    internal_last_updated_timestamp TIMESTAMP(6)
);
```

### Messages Table

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role message_role NOT NULL,  -- USER or ASSISTANT
    message_index INTEGER NOT NULL,
    content BYTEA NOT NULL,  -- JSON as bytes
    rating VARCHAR(24),
    created_timestamp TIMESTAMP(6),
    UNIQUE(conversation_id, message_index)
);
```

### Responses Table

```sql
CREATE TABLE responses (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    status response_status NOT NULL,  -- in_progress, completed, failed
    background BOOLEAN NOT NULL,
    created_timestamp TIMESTAMP(6),
    completed_timestamp TIMESTAMP(6),
    current_progress TEXT,
    final_output JSONB,
    error_message TEXT
);
```

## Project Structure

```
agent-backend/
├── databricks.yml              # Asset bundle configuration
├── app.yaml                    # App runtime config
├── pyproject.toml             # Dependencies
├── alembic.ini                # Alembic configuration
├── server/
│   ├── main.py                # FastAPI app
│   ├── responses_handler.py   # /responses endpoint
│   ├── config.py              # Environment config
│   ├── auth/
│   │   └── databricks.py      # WorkspaceClient OAuth
│   ├── db/
│   │   ├── connection.py      # Async connection pool
│   │   ├── models.py          # SQLAlchemy models
│   │   └── queries.py         # CRUD operations
│   ├── llm/
│   │   └── client.py          # OpenAI client wrapper
│   └── schemas/
│       ├── estore.py          # Estore types
│       └── responses.py       # OpenResponses types
├── migrations/
│   ├── env.py                 # Alembic environment
│   └── versions/              # Migration scripts
└── scripts/
    └── migrate.py             # Run migrations
```

## Development

### Run Tests

```bash
uv run pytest
```

### Create New Migration

```bash
alembic revision --autogenerate -m "Add new column"
```

### Apply Migrations

```bash
python scripts/migrate.py
```

### View Logs (Deployed App)

```bash
databricks apps logs <app-name> --follow
```

## OpenAI Client Compatibility

This backend can be used with the OpenAI Python SDK:

```python
from databricks_openai import DatabricksOpenAI

client = DatabricksOpenAI()

# Call our backend endpoint
response = client.responses.create(
    model="databricks-gpt-5-2",
    input=[{"role": "user", "content": "Hello"}],
    stream=True
)

for chunk in response:
    print(chunk)
```

## Next Steps

This prototype validates the core runtime architecture. Future enhancements:

1. **Declarative YAML spec support** - Define agents via config files
2. **Tool orchestration** - Add MAS patterns for parallel tool execution
3. **Production hardening** - Error handling, rate limiting, monitoring
4. **UI integration** - Connect e2e-chatbot-app-next frontend

## References

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses)
- [Databricks Apps Documentation](https://docs.databricks.com/en/dev-tools/databricks-apps.html)
- [MLflow OpenResponses API](https://mlflow.org/docs/latest/openresponses.html)
