# Declarative Agent SDK - Examples

This directory contains examples demonstrating the Declarative Agent SDK.

## Prerequisites

1. **Start the backend server:**
   ```bash
   cd ..
   DB_TYPE=sqlite uvicorn server.main:app --host 0.0.0.0 --port 8000
   ```

2. **Install SDK dependencies:**
   ```bash
   pip install openai pydantic pyyaml
   ```

## Examples

### 1. Basic Usage (`basic_usage.py`)

Demonstrates the three execution modes:

```bash
python basic_usage.py
```

**Features:**
- ✓ Non-streaming responses
- ✓ Streaming responses with real-time output
- ✓ Background mode for long-running tasks

### 2. Background Agent (`background_agent.py`)

Shows how to use background mode for complex analysis tasks:

```bash
python background_agent.py
```

**Features:**
- ✓ Submit tasks in background
- ✓ Retrieve completed results
- ✓ Continue conversations with follow-up questions
- ✓ Uses the data analyst agent with specific instructions

## Agent Definitions

### `agents/assistant.yaml`

A general-purpose helpful assistant with balanced temperature settings.

**Use Cases:**
- General Q&A
- Information lookup
- Casual conversation

### `agents/data_analyst.yaml`

An analytical agent optimized for data tasks with lower temperature for consistency.

**Use Cases:**
- Data exploration
- Statistical analysis
- Report generation
- Long-running computations (background mode)

## Creating Custom Agents

1. **Copy a template:**
   ```bash
   cp agents/assistant.yaml agents/my_agent.yaml
   ```

2. **Edit the configuration:**
   ```yaml
   name: "my-custom-agent"
   description: "My custom agent"

   model: "databricks-gpt-5-2"
   temperature: 0.5  # Adjust for your use case

   instructions: |
     Your custom system instructions here...
   ```

3. **Use in your code:**
   ```python
   agent = DeclarativeAgent.from_yaml(
       "agents/my_agent.yaml",
       backend_url="http://localhost:8000"
   )
   ```

## Running Examples

Make sure the backend is running first:

```bash
# Terminal 1: Start backend
cd ..
DB_TYPE=sqlite SQLITE_DATABASE=/tmp/test_agent_backend.db \
  uvicorn server.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Run examples
cd examples
python basic_usage.py
python background_agent.py
```

## Troubleshooting

### Connection Errors

If you see connection errors:
```
Error: Connection refused
```

Make sure the backend is running on port 8000:
```bash
curl http://localhost:8000/health
```

### Import Errors

If you see import errors:
```
ModuleNotFoundError: No module named 'declarative_agent'
```

The examples automatically add the SDK to the path. Make sure you're running from the `examples/` directory.

## Next Steps

- Explore the SDK API in `sdk/README.md`
- Create custom agents for your use cases
- Integrate with your applications
- Deploy agents to production using Databricks Apps

## Architecture

```
┌─────────────────────────────────────────────┐
│         Your Application                     │
│                                              │
│  from declarative_agent import               │
│    DeclarativeAgent, AgentRunner             │
│                                              │
│  agent = DeclarativeAgent.from_yaml(...)     │
│  runner = AgentRunner(agent, user_id)        │
│  response = await runner.run(message)        │
│                                              │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
      ┌────────────────────────┐
      │  OpenResponses API      │
      │  (localhost:8000)       │
      │                         │
      │  POST /v1/responses     │
      │  GET /v1/responses/{id} │
      └───────────┬─────────────┘
                  │
                  ↓
      ┌───────────────────────┐
      │   Databricks LLM      │
      │   (gpt-5-2)           │
      └───────────────────────┘
```
