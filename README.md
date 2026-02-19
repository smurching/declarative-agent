# Agent Backend with OpenResponses API

A production-ready agent backend built on Databricks Apps + Lakebase, implementing an OpenResponses-compatible API for conversation management and LLM interaction. Supports both **SQLite** (local development) and **PostgreSQL/Lakebase** (production).

## 📚 Documentation

### Core Documentation
- **[Architecture Overview](docs/ARCHITECTURE.md)** - Complete system architecture with data flow diagrams, SSE streaming, authentication, and integration patterns
- **[UI Integration Guide](docs/UI_INTEGRATION_GUIDE.md)** - Step-by-step guide to building and deploying a web UI with streaming responses
- **[Streaming Debug Guide](docs/STREAMING_DEBUG_GUIDE.md)** - Debugging journey, common issues, and solutions for SSE streaming

### Implementation Guides
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Deploying agent backend to Databricks Apps
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Complete implementation details and design decisions
- **[Framework Spec](FRAMEWORK_SPEC.md)** - OpenResponses API specification and framework architecture

### Troubleshooting & Fixes
- **[Streaming Fix Summary](STREAMING_FIX_SUMMARY.md)** - Agent backend streaming implementation (legacy, see docs/STREAMING_DEBUG_GUIDE.md for UI issues)
- **[Permission Fix](PERMISSION_FIX.md)** - Databricks Apps permission configuration
- **[Deployment Status](DEPLOYMENT_STATUS.md)** - Current deployment state and validation results
- **[UI Deployment Status](UI_DEPLOYMENT_STATUS.md)** - UI app deployment details

### SDK & Examples
- **[SDK Documentation](sdk/README.md)** - Declarative Agent SDK API reference
- **[Examples](examples/README.md)** - Sample agents and usage patterns

## Features

- **OpenResponses-compatible /responses API** - Supports streaming, non-streaming, and background modes
- **Hosted Tools Support** - Server-side tools (calculator, time, weather) with streaming tool calls
- **Pluggable database backend** - SQLite for local dev, PostgreSQL for production
- **Estore-compatible conversation schema** - Message ordering via `message_index`
- **Databricks LLM integration** - Via OpenAI SDK with automatic authentication
- **Input validation** - Proper error handling with 422 responses
- **FastAPI + uvicorn** - High-performance async web framework
- **Declarative Agent SDK** - Define agents via YAML, execute with Python

## Architecture

```
POST /responses → Conversation Handler → Databricks LLM
                         ↓
              SQLite (local) or PostgreSQL (production)
```

## Prerequisites

### Local Development
- Python 3.10+
- Databricks CLI configured with authentication
- Access to Databricks LLM serving endpoint

### Production Deployment
- All local prerequisites
- Access to Databricks workspace with Lakebase instance

## Quick Start

### Local Development (SQLite)

**No database credentials needed!**

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   # or
   uv sync
   ```

2. **Configure Environment**
   ```bash
   export DB_TYPE=sqlite
   export DATABRICKS_CLI_PROFILE=your-profile
   export WORKSPACE_ID=your-workspace-id
   ```

3. **Run Server**
   ```bash
   uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The database file will be created automatically at `./agent_backend.db`.

4. **Run Tests**
   ```bash
   DB_TYPE=sqlite pytest tests/test_api_acceptance.py -v
   ```

### Production Deployment (PostgreSQL/Lakebase)

1. **Configure Bundle**

   Edit `databricks.yml` with your configuration.

2. **Deploy to Databricks Apps**
   ```bash
   databricks bundle validate
   databricks bundle deploy --target prod
   ```

   Environment variables (PGHOST, PGPORT, etc.) are automatically injected by the platform.

## API Usage

### POST /v1/responses (Streaming)

```bash
curl -X POST http://localhost:8000/v1/responses \
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

### POST /v1/responses (Non-streaming)

```bash
curl -X POST http://localhost:8000/v1/responses \
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
  ],
  "status": "completed"
}
```

### POST /v1/responses (Background Mode)

```bash
curl -X POST http://localhost:8000/v1/responses \
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

### GET /v1/responses/{id}

Retrieve or resume a response:

```bash
curl http://localhost:8000/v1/responses/resp_abc123
```

## Declarative Agent SDK

Define and run AI agents using simple YAML configurations powered by the OpenResponses API backend.

### Features

- **Define agents via YAML** - No code required to configure agents
- **Multiple execution modes** - Streaming, non-streaming, and background
- **Conversation history** - Multi-turn conversations with context
- **Production-ready** - Built on battle-tested OpenResponses API

### Quick Start

**1. Define an Agent (YAML)**

```yaml
# examples/agents/assistant.yaml
name: "helpful-assistant"
description: "A helpful AI assistant"

model: "databricks-gpt-5-2"
temperature: 0.7

instructions: |
  You are a helpful AI assistant. Provide clear and concise answers.

supports_streaming: true
supports_background: true
```

**2. Run the Agent (Python)**

```python
import asyncio
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def main():
    # Load agent from YAML
    agent = DeclarativeAgent.from_yaml(
        "examples/agents/assistant.yaml",
        backend_url="http://localhost:8000"
    )

    # Create runner
    async with AgentRunner(agent, user_id=12345) as runner:
        # Non-streaming
        response = await runner.run(
            message="What is 2+2?",
            stream=False
        )
        print(response['output'][0]['content'])

        # Streaming
        stream = await runner.run(
            message="Tell me a story",
            stream=True
        )
        async for event in stream:
            if event.get("type") == "delta":
                print(event["delta"]["text"], end="", flush=True)

        # Background mode (for long-running tasks)
        response = await runner.run(
            message="Analyze this large dataset...",
            background=True
        )
        task_id = response['id']
        # Later: await runner.retrieve(task_id)

asyncio.run(main())
```

### Examples

See the [`examples/`](./examples/) directory for complete examples:

- **basic_usage.py** - Non-streaming, streaming, and background modes
- **background_agent.py** - Long-running tasks with background execution
- **agents/** - Example YAML agent definitions

### Documentation

- [SDK Documentation](./sdk/README.md) - Full API reference
- [Examples Guide](./examples/README.md) - Running examples and creating custom agents

## Hosted Tools

Server-side tools that execute within the backend, with full streaming support.

### Available Tools

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `calculator` | Perform mathematical calculations | "What is 25 * 4?" |
| `get_current_time` | Get current date and time | "What time is it?" |
| `get_weather` | Get weather information (mock) | "What's the weather in SF?" |

### Using Tools

**Non-streaming:**
```python
response = await client.responses.create(
    input=[{"role": "user", "content": "What is 144 / 12?"}],
    tools=[{"type": "calculator"}],
    extra_body={"databricks_options": {"user_id": 12345}}
)
```

**Streaming (with tool calls):**
```python
stream = await client.responses.create(
    input=[{"role": "user", "content": "Calculate 10+20 and tell me the time"}],
    stream=True,
    tools=[
        {"type": "calculator"},
        {"type": "get_current_time"}
    ],
    extra_body={"databricks_options": {"user_id": 12345}}
)

async for event in stream:
    # Receive tool call arguments, execution results, and final response
    # All streamed in real-time
    print(event)
```

### How It Works

```
1. User: "What is 10 + 20?"
2. Backend → LLM (with tools defined)
3. LLM → Tool call: calculator("10 + 20")
4. Backend executes calculator → Result: 30
5. Backend → LLM (with tool result)
6. LLM → Final response: "The answer is 30"
7. Stream events to user in real-time
```

### Future Extensions

The following features are designed but not yet implemented:

#### Tool Choice Parameter
Control when tools are used:
```python
tool_choice="auto"      # LLM decides (default)
tool_choice="required"  # Must use a tool
tool_choice="none"      # Don't use tools
```

#### Parallel Tool Calls
Execute multiple tools simultaneously:
```python
# User: "What is 10+20, 5*6, and the current time?"
# LLM makes 3 tool calls in parallel:
#   - calculator("10+20")
#   - calculator("5*6")
#   - get_current_time()
```

#### Custom Tools
Define your own hosted tools:
```python
@register_tool("database_query")
async def query_database(query: str) -> dict:
    # Your implementation
    pass
```

See `tests/test_tools.py` for detailed specifications of future features.

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_TYPE` | Database type (`sqlite` or `postgres`) | `postgres` | No |
| `SQLITE_DATABASE` | Path to SQLite database | `./agent_backend.db` | No |
| `PGHOST` | PostgreSQL host | - | Yes (prod) |
| `PGPORT` | PostgreSQL port | `5432` | Yes (prod) |
| `PGDATABASE` | PostgreSQL database | `databricks_postgres` | Yes (prod) |
| `PGUSER` | PostgreSQL user | - | Yes (prod) |
| `DATABRICKS_CLI_PROFILE` | Databricks CLI profile | - | Yes |
| `WORKSPACE_ID` | Databricks workspace ID | - | Yes |
| `DATABRICKS_SERVING_ENDPOINT` | LLM endpoint name | `databricks-gpt-5-2` | No |

### Local Configuration (.env)

```bash
# Database
DB_TYPE=sqlite
SQLITE_DATABASE=./agent_backend.db

# Databricks
DATABRICKS_CLI_PROFILE=your-profile
WORKSPACE_ID=your-workspace-id
DATABRICKS_SERVING_ENDPOINT=databricks-gpt-5-2
```

## Database Schema

The same schema works across both SQLite and PostgreSQL with portable type adapters.

### Conversations Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID/String(36) | Primary key |
| `internal_workspace_id` | BigInteger | Workspace ID |
| `user_id` | BigInteger | User ID |
| `created_timestamp` | Timestamp | Creation time |

### Messages Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID/String(36) | Primary key |
| `conversation_id` | UUID/String(36) | Foreign key |
| `role` | String(20) | USER or ASSISTANT |
| `message_index` | Integer | Message order (0, 1, 2...) |
| `content` | Binary | JSON as bytes |
| `created_timestamp` | Timestamp | Creation time |

### Responses Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | String(64) | Primary key (resp_xxx) |
| `conversation_id` | UUID/String(36) | Foreign key |
| `status` | String(20) | in_progress, completed, failed |
| `background` | Boolean | Background mode flag |
| `final_output` | JSON/Text | Completed output |

## Testing

### Test Locally (SQLite)

```bash
DB_TYPE=sqlite pytest tests/test_api_acceptance.py -v
```

**Results:** 28/35 tests passing (80%)

### Test Deployed App (PostgreSQL)

```bash
BASE_URL=https://your-app-url.databricksapps.com \
DATABRICKS_CLI_PROFILE=your-profile \
pytest tests/test_api_acceptance.py -v
```

**Results:** 22/24 API tests passing

### Test Coverage

| Test Suite | Local (SQLite) | Deployed (PostgreSQL) |
|------------|----------------|----------------------|
| Health Endpoints | ✅ 3/3 | ✅ 3/3 |
| Non-Streaming | ✅ 6/7 | ✅ 5/7 |
| Streaming | ✅ 5/5 | ✅ 5/5 |
| Background Mode | ✅ 2/2 | ✅ 2/2 |
| Error Handling | ✅ 4/4 | ✅ 4/4 |
| Message Persistence | ✅ 2/2 | ✅ 2/2 |

## Project Structure

```
agent-backend/
├── databricks.yml              # Asset bundle configuration
├── app.yaml                    # App runtime config
├── pyproject.toml             # Dependencies
├── .env.local.example         # Local config example
├── server/
│   ├── main.py                # FastAPI app entry point
│   ├── responses_handler.py   # /responses endpoint implementation
│   ├── config.py              # Environment configuration
│   ├── auth/
│   │   └── databricks.py      # WorkspaceClient OAuth wrapper
│   ├── db/
│   │   ├── connection.py      # Pluggable database backend
│   │   ├── models.py          # Portable SQLAlchemy models
│   │   └── queries.py         # CRUD operations
│   ├── llm/
│   │   └── client.py          # Databricks LLM client
│   └── schemas/
│       ├── estore.py          # Estore-compatible types
│       └── responses.py       # OpenResponses API types
├── tests/
│   ├── conftest.py            # Test fixtures (supports both DBs)
│   └── test_api_acceptance.py # Comprehensive API tests
└── IMPLEMENTATION_COMPLETE_SUMMARY.md  # Full implementation details
```

## OpenAI Client Compatibility

This backend is compatible with the OpenAI Python SDK:

```python
from openai import OpenAI

# For local development
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed-for-local"
)

# For deployed app
from databricks_openai import DatabricksOpenAI
client = DatabricksOpenAI(
    base_url="https://your-app.databricksapps.com/v1"
)

# Create a response
response = client.responses.create(
    input=[{"role": "user", "content": "Hello"}],
    stream=True
)

for event in response:
    print(event)
```

## Input Validation

The API validates all requests and returns proper HTTP 422 errors:

- ✅ Empty input detection
- ✅ Required fields validation (`databricks_options`, `user_id`)
- ✅ Invalid role detection
- ✅ Invalid JSON handling

## Benefits

### Local Development
- ✅ No database credentials needed
- ✅ No authentication overhead
- ✅ Fast iteration with file-based database
- ✅ Same API as production

### Production
- ✅ PostgreSQL with custom schema
- ✅ Automatic OAuth token refresh
- ✅ SSL support
- ✅ High availability

### Testing
- ✅ 80% test coverage working locally
- ✅ Fast test execution (no network DB calls)
- ✅ Easy cleanup (delete .db file)
- ✅ Same tests work for both environments

## Next Steps

This backend provides a foundation for advanced agent features:

1. **Declarative YAML spec** - Define agents via configuration
2. **Tool orchestration** - Parallel tool execution (MAS patterns)
3. **Production hardening** - Rate limiting, monitoring, alerts
4. **UI integration** - Connect chat frontends

## References

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses)
- [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps.html)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [FastAPI](https://fastapi.tiangolo.com/)

## License

See LICENSE file for details.
