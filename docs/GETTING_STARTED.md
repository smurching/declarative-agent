# Getting Started with Declarative Agents

Build and deploy AI agents using simple YAML configuration files. No complex framework setup required—just define your agent's behavior, connect it to tools, and deploy.

## What is a Declarative Agent?

A declarative agent is an AI assistant defined through YAML configuration rather than code. You specify:

- **What the agent does** - Instructions and system prompts
- **Which model to use** - Model name, temperature, token limits
- **Available tools** - Database access, code execution, vector search
- **How it runs** - Streaming, non-streaming, or background modes

The framework handles all the complexity: LLM interactions, conversation state, tool orchestration, authentication, and streaming.

## Architecture Overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Python    │─────▶│ Declarative  │─────▶│  Backend    │
│     SDK     │◀─────│    Agent     │◀─────│     API     │
└─────────────┘      │  (YAML def)  │      │ (/responses)│
  Your Code          └──────────────┘      └─────────────┘
                           │                       │
                           ▼                       ▼
                     Agent Runner            Databricks
                    (Conversation            LLM Serving
                    Management)              Endpoint
```

**Three-layer stack:**
1. **Agent Definition** (YAML) - Declarative configuration
2. **Agent Runner** (Python SDK) - Execution and state management
3. **Backend API** (FastAPI) - LLM interaction and tool execution

## Quick Start (5 Minutes)

### Prerequisites

- Python 3.10+
- Databricks CLI configured with authentication
- Access to Databricks workspace

### Step 1: Install Dependencies

```bash
cd ~/declarative-agent
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Create .env file
export DB_TYPE=sqlite
export DATABRICKS_CLI_PROFILE=your-profile
export WORKSPACE_ID=your-workspace-id
```

### Step 3: Start the Backend

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend provides the `/v1/responses` API that your agent will use.

### Step 4: Run Your First Agent

Create a simple Python script:

```python
import asyncio
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def main():
    # Load pre-built assistant agent
    agent = DeclarativeAgent.from_yaml(
        "examples/agents/assistant.yaml",
        backend_url="http://localhost:8000"
    )

    # Run the agent
    async with AgentRunner(agent, user_id=12345) as runner:
        response = await runner.run(
            message="What is 2+2?",
            stream=False
        )
        print(response['output'][0]['content'])

asyncio.run(main())
```

**Output:**
```
The answer is 4.
```

✅ **Success!** You've just run your first declarative agent.

## Define Your Own Agent

### Basic Agent Structure

Create `my_agent.yaml`:

```yaml
name: "my-assistant"
description: "My first AI assistant"

# Model configuration
model: "databricks-gpt-5-2"
temperature: 0.7

# What the agent does
instructions: |
  You are a helpful AI assistant. Provide clear, concise answers.
  Be friendly and professional.

# Execution modes
supports_streaming: true
supports_background: true
```

### Agent Configuration Options

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Agent identifier | `"customer-support"` |
| `description` | What the agent does | `"Helps customers with questions"` |
| `model` | Databricks LLM endpoint | `"databricks-gpt-5-2"` |
| `temperature` | Creativity (0.0-1.0) | `0.7` |
| `instructions` | System prompt | Multiline string |
| `supports_streaming` | Enable streaming mode | `true`/`false` |
| `supports_background` | Enable background mode | `true`/`false` |

### Example: Customer Support Agent

```yaml
name: "customer-support"
description: "Customer support agent for product questions"

model: "databricks-gpt-5-2"
temperature: 0.7
max_output_tokens: 2048

instructions: |
  You are a friendly customer support agent for TechCorp products.

  Your role:
  - Answer product questions clearly and accurately
  - Help troubleshoot common issues
  - Escalate complex problems to human agents
  - Always be polite and professional

  Guidelines:
  - Keep responses concise (2-3 sentences when possible)
  - Use bullet points for multi-step instructions
  - Ask clarifying questions if needed
  - Don't make up information - say "I don't know" if uncertain

supports_streaming: true
supports_background: false

metadata:
  version: "1.0"
  team: "customer-success"
```

## Local Development

### Running Agents Locally

The SDK provides three execution modes:

#### 1. Non-Streaming (Simple Responses)

Best for: Short questions, quick answers

```python
import asyncio
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def main():
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Get complete response at once
        response = await runner.run(
            message="What is the capital of France?",
            stream=False
        )

        print(response['output'][0]['content'])
        # Output: "The capital of France is Paris."

asyncio.run(main())
```

#### 2. Streaming (Real-time Text)

Best for: Long responses, interactive chat

```python
async def main():
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Stream response token-by-token
        stream = await runner.run(
            message="Tell me a story about a robot",
            stream=True
        )

        # Print each chunk as it arrives
        async for event in stream:
            if event.get("type") == "delta" and "delta" in event:
                if "text" in event["delta"]:
                    print(event["delta"]["text"], end="", flush=True)

        print()  # New line when done

asyncio.run(main())
```

#### 3. Background Mode (Long Tasks)

Best for: Complex analysis, report generation, large datasets

```python
async def main():
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Submit task in background
        response = await runner.run(
            message="Analyze sales data for Q4 and create report",
            background=True
        )

        task_id = response['id']
        print(f"Task submitted: {task_id}")
        print(f"Status: {response['status']}")  # "in_progress"

        # Later: retrieve results
        # result = await runner.retrieve(task_id)

asyncio.run(main())
```

### Multi-Turn Conversations

Agents automatically maintain conversation history:

```python
async def main():
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # First message
        resp1 = await runner.run(
            message="My name is Alice",
            stream=False
        )
        print(resp1['output'][0]['content'])
        # "Nice to meet you, Alice!"

        # Follow-up - agent remembers context
        resp2 = await runner.run(
            message="What's my name?",
            stream=False
        )
        print(resp2['output'][0]['content'])
        # "Your name is Alice."

asyncio.run(main())
```

### Testing Your Agent

Create test scripts to validate behavior:

```python
# test_my_agent.py
import asyncio
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def test_basic_qa():
    """Test basic question answering."""
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        response = await runner.run(
            message="What is 2+2?",
            stream=False
        )

        content = response['output'][0]['content']
        assert "4" in content, f"Expected '4' in response: {content}"
        print("✓ Basic QA test passed")

async def test_conversation_memory():
    """Test conversation context retention."""
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        # Set context
        await runner.run(message="I like pizza", stream=False)

        # Test recall
        response = await runner.run(
            message="What food do I like?",
            stream=False
        )

        content = response['output'][0]['content'].lower()
        assert "pizza" in content, f"Expected 'pizza' in response: {content}"
        print("✓ Conversation memory test passed")

if __name__ == "__main__":
    asyncio.run(test_basic_qa())
    asyncio.run(test_conversation_memory())
```

Run tests:
```bash
python test_my_agent.py
```

## Deployment to Databricks

### Step 1: Create Databricks Bundle

Create `databricks.yml`:

```yaml
bundle:
  name: my-agent-project

variables:
  serving_endpoint_name:
    default: "databricks-gpt-5-2"

resources:
  apps:
    # Backend API
    agent_backend:
      name: "${bundle.target}-backend"
      description: "Agent backend with /v1/responses API"
      source_code_path: ./

      resources:
        - name: serving-endpoint
          serving_endpoint:
            name: ${var.serving_endpoint_name}
            permission: CAN_QUERY

    # Agent application (optional - if you want to deploy agent as API)
    my_agent:
      name: "${bundle.target}-my-agent"
      description: "My custom agent"
      source_code_path: ./agent_app

      config:
        command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
        env:
          - name: BACKEND_APP_URL
            value: "https://${bundle.target}-backend.databricksapps.com"

targets:
  dev:
    mode: development
    default: true

  prod:
    mode: production
```

### Step 2: Deploy

```bash
# Validate configuration
databricks bundle validate

# Deploy to development
databricks bundle deploy --target dev

# Deploy to production
databricks bundle deploy --target prod
```

### Step 3: Test Deployed Agent

```python
import asyncio
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def main():
    # Point to deployed backend
    agent = DeclarativeAgent.from_yaml(
        "my_agent.yaml",
        backend_url="https://dev-backend.databricksapps.com"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        response = await runner.run(
            message="Hello from production!",
            stream=False
        )
        print(response['output'][0]['content'])

asyncio.run(main())
```

## Execution Modes Comparison

| Feature | Non-Streaming | Streaming | Background |
|---------|---------------|-----------|------------|
| **Use Case** | Short answers | Interactive chat | Long tasks |
| **Response Time** | Wait for complete response | Immediate, incremental | Async, poll for results |
| **User Experience** | Simple, synchronous | Real-time feedback | Submit and forget |
| **Best For** | APIs, batch jobs | Chat interfaces | Reports, analysis |
| **Example** | "What is 2+2?" | "Write a story" | "Analyze 1M records" |

### When to Use Each Mode

**Non-Streaming:**
- Short, factual questions
- API integrations where you need complete response
- Batch processing multiple queries
- Testing and development

**Streaming:**
- Chat interfaces and conversational UI
- Long-form content generation
- Real-time user feedback important
- Token-by-token display desired

**Background:**
- Data analysis over large datasets
- Report generation (multi-page documents)
- Tasks taking >30 seconds
- User doesn't need to wait for results

## Next Steps

### Learn More

- **[End-to-End Example](END_TO_END_EXAMPLE.md)** - Build a complete customer support agent from scratch
- **[UI Integration](UI_INTEGRATION_GUIDE.md)** - Deploy a web chat interface for your agent
- **[Architecture Guide](ARCHITECTURE.md)** - Deep dive into system design and data flow
- **[SDK Documentation](../sdk/README.md)** - Complete API reference

### Add Advanced Features

1. **Tools and Functions** - Connect your agent to databases, APIs, code execution
   - See `examples/agents/data_analyst.yaml` for UC table access
   - Add custom tools via Python functions

2. **Multi-Agent Systems** - Combine multiple specialized agents
   - Use background mode for agent-to-agent communication
   - Orchestrate complex workflows

3. **Observability** - Track agent performance and behavior
   - Enable tracing to Databricks tables
   - Collect user feedback

4. **Governance** - Control costs, rate limits, and access
   - Set cost limits per session
   - Configure rate limiting
   - Define access control policies

### Example Agents to Explore

All examples in `examples/agents/`:

- **assistant.yaml** - Simple helpful assistant (start here)
- **data_analyst.yaml** - SQL queries + Python analysis with tools
- **code_reviewer.yaml** - Code review and suggestions
- **hr_support.yaml** - Employee Q&A with company policies
- **sales_assistant.yaml** - Sales support with CRM access

Run any example:
```bash
python examples/basic_usage.py
```

### Get Help

- **Issues & Questions** - Check the main README for support links
- **Examples** - Browse `examples/` directory for working code
- **Documentation** - See `docs/` for detailed guides

---

**Ready to build?** Start with the [End-to-End Example](END_TO_END_EXAMPLE.md) to create your first production-ready agent with a web UI.
