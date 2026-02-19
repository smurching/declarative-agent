# Declarative Agent SDK

Define and run AI agents using simple YAML configurations powered by the OpenResponses API backend.

## Overview

The Declarative Agent SDK allows you to:
- **Define agents via YAML** - No code required to configure agents
- **Execute using OpenResponses API** - Powered by our production backend
- **Support multiple execution modes** - Streaming, non-streaming, and background
- **Maintain conversation history** - Multi-turn conversations with context

## Installation

```bash
# Install dependencies
pip install openai pydantic pyyaml

# Or add to your requirements.txt
openai>=1.0.0
pydantic>=2.0.0
pyyaml>=6.0.0
```

## Quick Start

### 1. Define an Agent (YAML)

Create `my_agent.yaml`:

```yaml
name: "helpful-assistant"
description: "A helpful AI assistant"

model: "databricks-gpt-5-2"
temperature: 0.7

instructions: |
  You are a helpful AI assistant. Provide clear and concise answers.

supports_streaming: true
supports_background: true
```

### 2. Run the Agent (Python)

```python
import asyncio
from declarative_agent import DeclarativeAgent, AgentRunner

async def main():
    # Load agent from YAML
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    # Create runner
    async with AgentRunner(agent, user_id=12345) as runner:
        # Run agent
        response = await runner.run(
            message="Hello! What can you help me with?",
            stream=False
        )

        print(response['output'][0]['content'])

asyncio.run(main())
```

## Agent Configuration

### YAML Schema

```yaml
name: string              # Required: Agent name
description: string       # Optional: Agent description
model: string             # LLM model (default: "databricks-gpt-5-2")
temperature: float        # Temperature 0.0-1.0 (default: 0.7)
instructions: string      # System instructions for the agent
supports_streaming: bool  # Enable streaming (default: true)
supports_background: bool # Enable background mode (default: true)
metadata: dict           # Additional metadata
```

## Execution Modes

### Non-Streaming Mode

Wait for complete response:

```python
response = await runner.run(
    message="What is 2+2?",
    stream=False
)

print(response['output'][0]['content'])  # "4"
```

### Streaming Mode

Process response chunks as they arrive:

```python
stream = await runner.run(
    message="Tell me a story",
    stream=True
)

async for event in stream:
    if event.get("type") == "delta":
        print(event["delta"]["text"], end="", flush=True)
```

### Background Mode

Submit long-running tasks:

```python
# Submit task
response = await runner.run(
    message="Analyze this large dataset...",
    background=True
)

task_id = response['id']
print(f"Task submitted: {task_id}")

# Later, retrieve result
result = await runner.retrieve(task_id)
print(result['status'])  # "completed"
```

## Multi-Turn Conversations

Continue conversations with context:

```python
# First message
response1 = await runner.run(
    message="My favorite color is blue",
    stream=False
)

conversation_id = response1['conversation_id']

# Follow-up message (with context)
response2 = await runner.run(
    message="What is my favorite color?",
    stream=False,
    conversation_id=conversation_id
)

print(response2['output'][0]['content'])  # "Your favorite color is blue"
```

## Examples

See the `examples/` directory for complete examples:

- **basic_usage.py** - Non-streaming, streaming, and background modes
- **background_agent.py** - Long-running tasks with background execution
- **agents/** - Example YAML agent definitions

## API Reference

### `DeclarativeAgent`

Main agent class for loading configurations.

```python
agent = DeclarativeAgent.from_yaml("agent.yaml", backend_url="http://localhost:8000")
```

### `AgentRunner`

Executes agents using the OpenResponses API.

```python
async with AgentRunner(agent, user_id=12345) as runner:
    response = await runner.run(message="Hello", stream=False)
```

#### Methods

- `run(message, stream=False, background=False, conversation_id=None)` - Execute agent
- `retrieve(response_id, stream=False)` - Retrieve response (for background tasks)
- `close()` - Close the client connection

## Architecture

```
YAML Agent Definition
        ↓
DeclarativeAgent (loads config)
        ↓
AgentRunner (executes via OpenResponses API)
        ↓
Backend (/v1/responses endpoint)
        ↓
Databricks LLM
```

## Requirements

- Python 3.10+
- Agent backend running on http://localhost:8000 (or configure custom URL)
- OpenAI SDK for API communication

## Development

```bash
# Run examples
cd examples
python basic_usage.py

# Create custom agents
mkdir my_agents
cp examples/agents/assistant.yaml my_agents/my_custom_agent.yaml
# Edit my_custom_agent.yaml
```

## License

MIT
