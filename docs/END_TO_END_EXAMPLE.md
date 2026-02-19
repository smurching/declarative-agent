# End-to-End Example: Customer Support Agent

Build a complete customer support agent from scratch, including backend, agent definition, and web chat UI—deployed to production in under 30 minutes.

## What You'll Build

**Scenario:** A customer support agent that helps users with product questions, troubleshooting, and order status.

**Components:**
1. **Backend API** - FastAPI server with `/v1/responses` endpoint
2. **Agent Definition** - YAML configuration for customer support behavior
3. **Web Chat UI** - React-based chat interface with streaming responses

**Final Result:**
```
User types: "How do I reset my password?"
Agent streams back: "To reset your password: 1. Go to Settings..."
```

---

## Part 1: Set Up the Backend (5 minutes)

The backend provides the `/v1/responses` API that handles LLM interactions, conversation state, and streaming.

### Step 1.1: Check Prerequisites

```bash
# Verify Python version
python --version  # Should be 3.10+

# Verify Databricks CLI
databricks --version

# Check authentication
databricks auth profiles
```

### Step 1.2: Navigate to Project

```bash
cd ~/declarative-agent
```

### Step 1.3: Install Dependencies

```bash
pip install -r requirements.txt
```

Expected packages:
- fastapi - Web framework
- uvicorn - ASGI server
- sqlalchemy - Database ORM
- openai - LLM client

### Step 1.4: Configure Environment

Create `.env` file:

```bash
# Database (use SQLite for local dev)
DB_TYPE=sqlite
SQLITE_DATABASE=./agent_backend.db

# Databricks authentication
DATABRICKS_CLI_PROFILE=your-profile-name
WORKSPACE_ID=your-workspace-id

# LLM endpoint
DATABRICKS_SERVING_ENDPOINT=databricks-gpt-5-2
```

**Get your workspace ID:**
```bash
databricks workspaces list
```

### Step 1.5: Start Backend Server

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 1.6: Test Backend

In a new terminal:

```bash
curl -X POST http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": false,
    "databricks_options": {"user_id": 12345}
  }'
```

**Expected response:**
```json
{
  "id": "resp_abc123",
  "output": [
    {"role": "assistant", "content": "Hello! How can I help you today?"}
  ],
  "status": "completed"
}
```

✅ **Backend is working!**

---

## Part 2: Define Your Agent (5 minutes)

Create a YAML file that defines your agent's behavior, personality, and capabilities.

### Step 2.1: Create Agent Definition

Create `examples/agents/customer_support.yaml`:

```yaml
name: "customer-support"
description: "Customer support agent for TechCorp products"

# Model configuration
model: "databricks-gpt-5-2"
temperature: 0.7
max_output_tokens: 2048

# Agent behavior and personality
instructions: |
  You are a friendly and helpful customer support agent for TechCorp.

  Your responsibilities:
  1. Answer product questions clearly and accurately
  2. Help customers troubleshoot common issues
  3. Provide order status information when asked
  4. Guide users through setup and configuration

  Guidelines:
  - Be warm, professional, and empathetic
  - Use clear, simple language (avoid jargon)
  - Break down complex instructions into numbered steps
  - If you don't know something, say so and offer to escalate
  - Always thank customers for their patience

  Common issues you can help with:
  - Password resets
  - Account setup
  - Billing questions
  - Product features and usage
  - Troubleshooting connectivity

  Things to escalate to human agents:
  - Refund requests over $100
  - Legal or compliance questions
  - Angry or upset customers (after initial de-escalation)
  - Technical bugs or system outages

# Execution modes
supports_streaming: true
supports_background: false

# Metadata
metadata:
  version: "1.0"
  team: "customer-success"
  last_updated: "2026-02-19"
```

### Step 2.2: Test Agent Locally

Create `test_support_agent.py`:

```python
"""Test the customer support agent."""

import asyncio
from pathlib import Path
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

async def test_password_reset():
    """Test password reset help."""
    agent = DeclarativeAgent.from_yaml(
        "examples/agents/customer_support.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        print("=" * 60)
        print("Testing: Password Reset Question")
        print("=" * 60)

        print("\nUser: How do I reset my password?")
        print("Agent: ", end="", flush=True)

        stream = await runner.run(
            message="How do I reset my password?",
            stream=True
        )

        async for event in stream:
            if event.get("type") == "delta" and "delta" in event:
                if "text" in event["delta"]:
                    print(event["delta"]["text"], end="", flush=True)

        print("\n")

async def test_conversation():
    """Test multi-turn conversation."""
    agent = DeclarativeAgent.from_yaml(
        "examples/agents/customer_support.yaml",
        backend_url="http://localhost:8000"
    )

    async with AgentRunner(agent, user_id=12345) as runner:
        print("=" * 60)
        print("Testing: Multi-turn Conversation")
        print("=" * 60)

        # Turn 1
        resp1 = await runner.run(
            message="I'm having trouble with my account",
            stream=False
        )
        print(f"\nUser: I'm having trouble with my account")
        print(f"Agent: {resp1['output'][0]['content']}")

        # Turn 2 - agent remembers context
        resp2 = await runner.run(
            message="It won't let me log in",
            stream=False
        )
        print(f"\nUser: It won't let me log in")
        print(f"Agent: {resp2['output'][0]['content']}")

        print("\n")

if __name__ == "__main__":
    print("\nCustomer Support Agent - Test Suite")
    print("=" * 60)
    print("\nMake sure backend is running: uvicorn server.main:app\n")

    asyncio.run(test_password_reset())
    asyncio.run(test_conversation())
```

Run the test:
```bash
python test_support_agent.py
```

**Expected output:**
```
Testing: Password Reset Question
============================================================

User: How do I reset my password?
Agent: To reset your password, follow these steps:

1. Go to the Settings page in your TechCorp account
2. Click on "Security" in the left sidebar
3. Select "Change Password"
4. Enter your current password
5. Enter and confirm your new password
6. Click "Update Password"

Your password must be at least 8 characters...

✅ Agent is responding correctly!
```

### Step 2.3: Iterate on Instructions

Based on testing, refine your agent's behavior:

```yaml
instructions: |
  # Add more specific examples
  Example interactions:

  User: "I can't log in"
  You: "I can help with that! Let's troubleshoot together.
       Are you receiving an error message, or is the page not loading?"

  User: "Where is my order?"
  You: "I'd be happy to check your order status! Could you provide
       your order number? It should be in your confirmation email
       and start with 'ORD-'."
```

Restart the test to verify changes.

---

## Part 3: Deploy to Production (10 minutes)

Deploy your backend and agent to Databricks Apps for production use.

### Step 3.1: Create Agent App

Create `agent_app/main.py`:

```python
"""Customer support agent FastAPI application."""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sdk.declarative_agent import DeclarativeAgent, AgentRunner

# Load agent from YAML
AGENT_PATH = Path(__file__).parent.parent / "examples/agents/customer_support.yaml"
BACKEND_URL = os.getenv("BACKEND_APP_URL", "http://localhost:8000")

agent = DeclarativeAgent.from_yaml(str(AGENT_PATH), backend_url=BACKEND_URL)

app = FastAPI(title="Customer Support Agent")


class InvocationsRequest(BaseModel):
    input: list[dict]  # [{"role": "user", "content": "..."}]
    stream: bool = True


@app.post("/invocations")
async def invocations(
    request: InvocationsRequest,
    authorization: str = Header(None)
):
    """Main agent endpoint."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")

    # Extract user message
    user_message = None
    for msg in request.input:
        if msg.get("role") == "user":
            user_message = msg.get("content")
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message")

    # Run agent
    user_id = 12345  # In production, extract from auth token
    async with AgentRunner(agent, user_id=user_id) as runner:
        if request.stream:
            async def stream_events():
                stream = await runner.run(message=user_message, stream=True)
                async for event in stream:
                    import json
                    yield f"data: {json.dumps(event)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream"
            )
        else:
            response = await runner.run(
                message=user_message,
                stream=False
            )
            return response


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": agent.name}
```

### Step 3.2: Create Databricks Bundle

Create `databricks.yml`:

```yaml
bundle:
  name: customer-support-agent

variables:
  serving_endpoint_name:
    default: "databricks-gpt-5-2"

resources:
  apps:
    # Backend API
    agent_backend:
      name: "${bundle.target}-backend"
      description: "Agent backend API"
      source_code_path: ./

      resources:
        - name: serving-endpoint
          serving_endpoint:
            name: ${var.serving_endpoint_name}
            permission: CAN_QUERY

    # Customer support agent
    customer_support_agent:
      name: "${bundle.target}-support-agent"
      description: "Customer support agent"
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

### Step 3.3: Deploy

```bash
# Validate bundle
databricks bundle validate

# Deploy to development
databricks bundle deploy --target dev
```

**Expected output:**
```
✓ Deployed dev-backend: https://dev-backend-xyz.databricksapps.com
✓ Deployed dev-support-agent: https://dev-support-agent-xyz.databricksapps.com
```

### Step 3.4: Test Deployed Agent

```bash
# Get auth token
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

# Test agent
curl -N "https://dev-support-agent-xyz.databricksapps.com/invocations" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {"role": "user", "content": "How do I contact support?"}
    ],
    "stream": true
  }'
```

**Expected:** Streaming SSE events with agent response

✅ **Agent is deployed and working in production!**

---

## Part 4: Add Web Chat UI (10 minutes)

Deploy a user-friendly chat interface so customers can interact with your agent.

### Step 4.1: Clone UI Template

```bash
cd ~/app-templates
git clone https://github.com/databricks/app-templates.git
cd app-templates/e2e-chatbot-app-next
```

### Step 4.2: Install Dependencies

```bash
npm install
```

### Step 4.3: Configure Environment

Create `.env`:

```bash
# Must match agent workspace!
DATABRICKS_CONFIG_PROFILE=your-profile-name

# Your deployed agent URL
API_PROXY=https://dev-support-agent-xyz.databricksapps.com/invocations

# LLM endpoint (for metadata)
DATABRICKS_SERVING_ENDPOINT=databricks-gpt-5-2

# Optional: debug logging
LOG_SSE_EVENTS=true
```

### Step 4.4: Test Locally

```bash
# Start dev server
npm run dev

# Opens at http://localhost:3000
```

Open your browser and test the chat:
1. Type: "How do I reset my password?"
2. Watch response stream in real-time
3. Follow up: "What if I forgot my email?"

✅ **Local UI is working!**

### Step 4.5: Deploy UI

Update `databricks.yml` in the UI project:

```yaml
bundle:
  name: customer-support-ui

resources:
  apps:
    chatbot_ui:
      name: "support-chat-${workspace.current_user.short_name}"
      description: "Customer support chat interface"
      source_code_path: .

      resources:
        - name: agent-app
          app:
            name: dev-support-agent
            permission: CAN_USE

targets:
  dev:
    mode: development
    workspace:
      host: https://your-workspace.cloud.databricks.com
```

Build and deploy:

```bash
# Build production bundle
npm run build

# Deploy to Databricks
databricks bundle deploy -t dev
```

**Output:**
```
✓ App deployed: https://support-chat-user-xyz.databricksapps.com
```

### Step 4.6: Grant Permissions

The UI app needs permission to call your agent:

```bash
# Get UI app's service principal
UI_SP=$(databricks apps get support-chat-user --output json | jq -r '.service_principal_client_id')

# Get auth token
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

# Grant permission
curl -X PUT "https://your-workspace.cloud.databricks.com/api/2.0/permissions/apps/dev-support-agent" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"access_control_list\": [
      {
        \"service_principal_name\": \"${UI_SP}\",
        \"permission_level\": \"CAN_USE\"
      }
    ]
  }"
```

---

## Part 5: Test End-to-End

### Step 5.1: Open Deployed UI

Navigate to: `https://support-chat-user-xyz.databricksapps.com`

### Step 5.2: Test Scenarios

**Test 1: Password Reset**
```
User: "I need to reset my password"
Expected: Step-by-step instructions, friendly tone
```

**Test 2: Order Status**
```
User: "Where is my order?"
Expected: Asks for order number, explains how to find it
```

**Test 3: Multi-turn Conversation**
```
User: "I'm having trouble with my account"
Agent: [responds with troubleshooting questions]
User: "I can't remember my username"
Agent: [remembers context, provides username recovery steps]
```

**Test 4: Escalation**
```
User: "I want a $500 refund"
Expected: Acknowledges request, explains escalation to human agent
```

### Step 5.3: Monitor Performance

Check agent logs:
```bash
databricks apps logs dev-support-agent --follow
```

Check UI logs:
```bash
databricks apps logs support-chat-user --follow
```

---

## Success Checklist

- ✅ Backend API running (local and deployed)
- ✅ Agent YAML defined with clear instructions
- ✅ Agent responds correctly to test scenarios
- ✅ Agent maintains conversation context
- ✅ Web UI deployed and accessible
- ✅ Streaming responses work in browser
- ✅ Multi-turn conversations work
- ✅ Service principal permissions configured

---

## What You Built

```
┌─────────────────────────────────────────────────────────┐
│                    Browser UI                            │
│              (support-chat-user)                         │
│   "How do I reset my password?" → [Submit]               │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              Customer Support Agent                      │
│           (dev-support-agent)                            │
│   • Loads customer_support.yaml                          │
│   • Applies instructions and personality                 │
│   • Maintains conversation context                       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                Backend API                               │
│              (dev-backend)                               │
│   • Handles /v1/responses requests                       │
│   • Manages conversation state in SQLite/PostgreSQL      │
│   • Streams responses from Databricks LLM                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│           Databricks LLM Serving                         │
│           (databricks-gpt-5-2)                           │
└─────────────────────────────────────────────────────────┘
```

---

## Next Steps

### Enhance Your Agent

**Add Tools:**
```yaml
# In customer_support.yaml, add:
tools:
  - type: function
    name: check_order_status
    description: "Look up order status by order number"
    function_name: tools.check_order_status
    permission: on_behalf_of_user
    approval_policy: always_allow
```

**Add Memory:**
```yaml
# Remember customer preferences and history
conversation:
  auto_compact: true
  memory:
    short_term: true  # Within conversation
    long_term:
      enabled: true   # Across conversations
```

**Add Observability:**
```yaml
# Track agent performance
tracing:
  enabled: true
  destination:
    type: table
    name: main.support.agent_traces

feedback:
  enabled: true
  destination:
    type: table
    name: main.support.agent_feedback
```

### Production Hardening

1. **Add cost limits:**
   ```yaml
   governance:
     max_cost_per_session: 0.50
     max_cost_per_user_per_day: 5.00
   ```

2. **Add rate limiting:**
   ```yaml
   governance:
     rate_limit:
       requests_per_minute: 10
       requests_per_hour: 100
   ```

3. **Add content safety:**
   ```yaml
   governance:
     content_safety:
       enabled: true
       block_pii_in_traces: true
   ```

4. **Add monitoring:**
   - Set up alerts for high costs
   - Monitor response times
   - Track user satisfaction scores

### Learn More

- **[Getting Started Guide](GETTING_STARTED.md)** - Core concepts and SDK reference
- **[UI Integration Guide](UI_INTEGRATION_GUIDE.md)** - Detailed UI deployment steps
- **[Architecture Guide](ARCHITECTURE.md)** - System design and data flow
- **[Example Agents](../examples/agents/)** - More agent templates

---

**Congratulations!** You've built a complete, production-ready customer support agent with a web chat interface. 🎉
