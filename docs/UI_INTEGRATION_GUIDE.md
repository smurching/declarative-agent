# UI Integration Guide: Building a Declarative Agent with Browser UI

Complete step-by-step guide to building and deploying a Databricks declarative agent with streaming browser UI integration.

## Overview

This guide walks through creating:
1. **Backend** - FastAPI server with OpenResponses /v1/responses API
2. **Agent App** - FastAPI app hosting a YAML-defined agent, with /invocations endpoint
3. **UI Server** - Express/Next.js app that bridges browser and agent
4. **Browser UI** - React chat interface with streaming text

**Architecture:**
```
Browser → UI Server → Agent App → Backend API → LLM
(React)   (Express)   (FastAPI)   (FastAPI)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed data flow and [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md) for troubleshooting.

---

## Part 1: Build the Declarative Agent

### Step 1.1: Project Structure

Create the following directory structure:

```
my-agent/
├── agent_app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app hosting the agent
│   └── examples/agents/
│       └── my_agent.yaml          # YAML agent definition
├── server/
│   ├── __init__.py
│   ├── main.py                    # Backend FastAPI server
│   ├── responses_handler.py       # OpenResponses streaming handler
│   ├── config.py                  # Configuration
│   ├── db/                        # Database layer
│   └── llm/                       # LLM client
├── sdk/
│   └── declarative_agent.py       # DeclarativeAgent SDK
├── databricks.yml                 # Asset bundle config
├── requirements.txt
└── .env
```

### Step 1.2: Define Your Agent (YAML)

The DeclarativeAgent SDK lets you define agents declaratively via YAML - no manual LangChain setup needed!

Create `agent_app/examples/agents/my_agent.yaml`:

```yaml
# My Agent Definition
name: my_agent
version: 1.0
description: "A helpful AI assistant"

# Model configuration
model: databricks-gpt-5-2
temperature: 0.7
max_output_tokens: 4096

# System prompt
prompt:
  system: |
    You are a helpful AI assistant. Provide clear, concise answers
    and help users with their questions.

# Tools (optional - add as needed)
tools: []
  # Example: UC function tool
  # - type: function
  #   name: calculator
  #   description: "Perform mathematical calculations"
  #   function_name: main.tools.calculator
  #   permission: on_behalf_of_user
  #   approval_policy: always_allow

# Agent behavior
behavior:
  recursion_limit: 10
  streaming: true
  interrupt_on_tool_approval: false

# Conversation settings
conversation:
  auto_compact: true
  compact_strategy: summarize
```

**For a comprehensive example with tools, tracing, and governance**, see [examples/agents/data_analyst.yaml](../examples/agents/data_analyst.yaml) which includes:
- UC table tools for SQL queries
- Code interpreter for Python analysis
- Vector search for finding similar analyses
- Tracing and feedback collection
- Cost limits and rate limits
- Content safety controls

### Step 1.3: Create Agent App (FastAPI)

The agent app hosts your YAML-defined agent and provides an `/invocations` endpoint that proxies to the backend.

Create `agent_app/main.py`:

```python
"""
Agent app FastAPI server.

Hosts a declarative agent defined in YAML and provides /invocations
endpoint that proxies requests to the backend /v1/responses API.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import DeclarativeAgent SDK
from sdk.declarative_agent import DeclarativeAgent, AgentRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AGENT_PATH = Path(__file__).parent / "examples/agents/my_agent.yaml"
BACKEND_URL = os.getenv("BACKEND_APP_URL", "http://localhost:8000")

# Load agent from YAML
agent = DeclarativeAgent.from_yaml(str(AGENT_PATH), backend_url=BACKEND_URL)

app = FastAPI(title="My Agent App")


class InvocationsRequest(BaseModel):
    """Request format for /invocations endpoint."""
    input: list[dict]  # [{"role": "user", "content": "..."}]
    stream: bool = True


async def verify_databricks_auth(
    authorization: Optional[str] = Header(None)
) -> bool:
    """
    Verify Databricks authentication.

    In production: validates OAuth token from Databricks Apps
    In local dev: accepts any token for testing
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    return True


@app.post("/invocations")
async def invocations(
    request: InvocationsRequest,
    authorized: bool = Depends(verify_databricks_auth)
):
    """
    Main endpoint for agent requests.

    Accepts OpenAI-style chat format:
        {"input": [{"role": "user", "content": "..."}], "stream": true}

    Returns OpenResponses SSE stream:
        data: {"type":"response.output_text.delta","delta":"..."}
        data: {"type":"response.output_item.done","item":{...}}
        data: [DONE]
    """
    try:
        # Extract user message and conversation history
        user_message = None
        conversation_id = None

        for msg in request.input:
            if msg.get("role") == "user":
                user_message = msg.get("content")

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Generate a user_id (in production, extract from auth token)
        user_id = 12345

        # Run agent using DeclarativeAgent SDK
        async with AgentRunner(agent, user_id=user_id) as runner:
            if request.stream:
                # Streaming mode - yield SSE events
                async def stream_events():
                    async for event in runner.run_streaming(
                        message=user_message,
                        conversation_id=conversation_id
                    ):
                        # Events are already in OpenResponses format
                        yield f"data: {json.dumps(event)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    stream_events(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no"
                    }
                )
            else:
                # Non-streaming mode - return complete response
                response = await runner.run(
                    message=user_message,
                    stream=False,
                    conversation_id=conversation_id
                )
                return response

    except Exception as e:
        logger.error(f"Error in invocations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "agent": agent.name}
```

**Key points:**
- Uses `DeclarativeAgent.from_yaml()` to load agent config
- `AgentRunner` handles conversation state and streaming
- No manual LangChain setup - SDK handles it all
- `/invocations` endpoint proxies to backend `/v1/responses`
- Returns OpenResponses SSE format expected by UI

### Step 1.4: Create Requirements

Create `requirements.txt`:

```
# FastAPI and server
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Backend dependencies (if using shared backend)
sqlalchemy>=2.0.0
pydantic>=2.0.0
httpx>=0.25.0

# LLM integration
openai>=1.0.0

# Utilities
python-dotenv>=1.0.0
```

**Note:** The actual DeclarativeAgent SDK and backend code should be in your repo. See [sdk/README.md](../sdk/README.md) for SDK documentation.

---

## Part 2: Deploy the Agent App

### Step 2.1: Create Databricks Asset Bundle

Create `databricks.yml` in the root of your project:

```yaml
bundle:
  name: my-agent-project

variables:
  serving_endpoint_name:
    default: "databricks-gpt-5-2"
  resource_name_suffix:
    default: "${bundle.target}"

resources:
  apps:
    # Backend app - provides /v1/responses API
    agent_backend:
      name: "${bundle.target}-backend"
      description: "Agent backend with OpenResponses API"
      source_code_path: ./

      # Resources needed by backend
      resources:
        - name: serving-endpoint
          serving_endpoint:
            name: ${var.serving_endpoint_name}
            permission: CAN_QUERY

    # Agent app - hosts the agent, calls backend
    my_agent_app:
      name: "${bundle.target}-agent"
      description: "My declarative agent"
      source_code_path: ./agent_app

      # Start command for FastAPI
      config:
        command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
        env:
          - name: BACKEND_APP_URL
            value: "https://${bundle.target}-backend-3217006663075879.aws.databricksapps.com"

      # Grant UI app permission (add after UI deployment)
      permissions: []
        # - service_principal_name: "app-xxxxx ui-app-name"
        #   level: CAN_USE

targets:
  dev:
    mode: development
    default: true
    variables:
      resource_name_suffix: "dev"
```

**Key configuration:**
- `command: ["uvicorn", "main:app", ...]` - Runs FastAPI with uvicorn (NOT Flask, NOT MLflow)
- `source_code_path: ./agent_app` - Agent app directory
- `BACKEND_APP_URL` - Points to your backend /v1/responses endpoint
- No MLflow wrappers needed - FastAPI deploys directly

### Step 2.2: Deploy Both Apps

```bash
# From project root

# 1. Validate configuration
databricks bundle validate

# 2. Deploy both backend and agent app
databricks bundle deploy -t dev

# 3. Check app status
databricks apps list
```

**Expected output:**
```
✓ Deployed agent-backend: https://dev-backend-3217006663075879.aws.databricksapps.com
✓ Deployed my-agent-app: https://dev-agent-3217006663075879.aws.databricksapps.com
```

### Step 2.3: Test Agent Directly

Test the `/invocations` endpoint:

```bash
# Get auth token
TOKEN=$(databricks auth token --host https://your-workspace.cloud.databricks.com --output json | jq -r '.access_token')

# Test agent app
curl -N "https://dev-agent-3217006663075879.aws.databricksapps.com/invocations" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "stream": true
  }'
```

**Expected output (OpenResponses SSE format):**
```
data: {"type":"response.output_text.delta","delta":"Hello"}
data: {"type":"response.output_text.delta","delta":"!"}
data: {"type":"response.output_text.delta","delta":" I'm"}
data: {"type":"response.output_text.delta","delta":" an"}
data: {"type":"response.output_text.delta","delta":" AI"}
...
data: {"type":"response.output_item.done","item":{"role":"assistant","content":"Hello! I'm an AI assistant..."}}
data: [DONE]
```

✅ **If you see streaming `response.output_text.delta` events, your agent app is working correctly!**

---

## Part 3: Build the UI

### Step 3.1: Clone UI Template with OpenResponses Support

**Option A: Use PR branch (recommended until PR merges)**

```bash
# Clone the template with OpenResponses support
git clone https://github.com/smurching/app-templates.git
cd app-templates/e2e-chatbot-app-next
git checkout feature/openresponses-support

# Install dependencies
npm install
```

**Option B: Use official template (after PR merges)**

```bash
git clone https://github.com/databricks/app-templates.git
cd app-templates/e2e-chatbot-app-next
npm install
```

**What's OpenResponses support?**

The e2e-chatbot-app-next template needs OpenResponses format support to work with declarative agents. This includes:
- `agent-client.ts` module for calling agent `/invocations` endpoints
- `parseOpenResponsesStream()` for parsing SSE events
- Proper UIMessageStream event schema (text-start, text-delta with IDs)

**PR:** [Add OpenResponses format streaming support](https://github.com/databricks/app-templates/compare/main...smurching:app-templates:feature/openresponses-support) (pending merge)

**⚠️ Note:** Until the PR merges, use the feature branch. Once merged, the official template will include OpenResponses support out-of-the-box.

### Step 3.2: Install Dependencies

```bash
npm install
```

### Step 3.3: Configure Environment

Create `.env` in the UI project:

```bash
# Databricks Authentication
# IMPORTANT: Must match agent app workspace!
DATABRICKS_CONFIG_PROFILE=your-profile-name

# Agent App URL (from Step 2.2)
API_PROXY="https://dev-agent-3217006663075879.aws.databricksapps.com/invocations"

# LLM Endpoint (for metadata only)
DATABRICKS_SERVING_ENDPOINT="databricks-gpt-5-2"

# Optional: Enable debug logging
LOG_SSE_EVENTS=true
```

**⚠️ Critical:** The `DATABRICKS_CONFIG_PROFILE` must point to the **same workspace** as your agent app. Tokens are workspace-specific!

### Step 3.4: Test Locally

```bash
# Start dev servers (client on 3000, server on 3001)
npm run dev

# In another terminal, run automated test
npx tsx tests/test_ui_streaming_debug.ts
```

**Expected output:**
```
Testing UI server streaming...
✓ Got response, reading stream...
[Event 1] start
[Event 2] text-start
[Event 3] text-delta
  └─ Text: "Hello"
[Event 4] text-delta
  └─ Text: "!"
...
✅ SUCCESS: Received streaming text content!
```

Open browser at `http://localhost:3000` and test the chat interface.

---

## Part 4: Configure Integration

### Step 4.1: Verify Server Integration

The UI template includes agent integration in `server/src/routes/chat.ts`. The key integration logic:

```typescript
// Call agent app
const agentResponse = await callAgentApp({
  url: process.env.API_PROXY!,  // Agent /invocations endpoint
  messages: uiMessages,
  conversationId: id,
  userId: session.user.email ?? session.user.id,
  token: agentToken,
});

// Convert OpenResponses format to UIMessageStream format
const textPartId = generateUUID();

writer.write({
  type: 'text-start',
  id: textPartId,  // Required by Vercel AI SDK
});

for await (const textDelta of parseOpenResponsesStream(agentResponse)) {
  writer.write({
    type: 'text-delta',
    id: textPartId,       // Same ID for all deltas
    delta: textDelta,     // Use 'delta', not 'textDelta'
  });
}
```

**Critical event schema:**
- `text-start` must have `id` field
- `text-delta` must have `id` and `delta` fields
- Use same `id` for all events in a response
- Use `delta`, NOT `textDelta` (schema validation)

### Step 4.2: Verify OpenResponses Parser

Check `packages/core/src/agent-client.ts`:

```typescript
export async function* parseOpenResponsesStream(
  response: Response
): AsyncGenerator<string> {
  // Parse SSE stream from agent app
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;

      const data = line.slice(6);
      if (data === '[DONE]') return;

      const event = JSON.parse(data);

      // Extract text from OpenResponses format
      if (event.type === 'response.output_text.delta' && event.delta) {
        yield event.delta;  // Yield text chunks
      } else if (event.type === 'response.error') {
        throw new Error(event.error?.message || 'Agent error');
      }
    }
  }
}
```

---

## Part 5: Deploy the UI

### Step 5.1: Configure Databricks Bundle

In UI project, create/update `databricks.yml`:

```yaml
bundle:
  name: my-chatbot-ui

variables:
  app_name:
    default: "chatbot-${workspace.current_user.short_name}"
  agent_url:
    default: "https://dev-agent-3217006663075879.aws.databricksapps.com/invocations"

resources:
  apps:
    chatbot_ui:
      name: ${var.app_name}
      description: "Chat UI for my agent"
      source_code_path: .

      # Grant permission to agent app
      resources:
        - name: agent-app
          app:
            name: dev-agent  # Your agent app name
            permission: CAN_USE

targets:
  dev:
    mode: development
    workspace:
      host: https://your-workspace.cloud.databricks.com
```

### Step 5.2: Update App Configuration

Update `app.yaml`:

```yaml
command: ["npm", "run", "start"]
runtime: nodejs20

env:
  - name: DATABRICKS_SERVING_ENDPOINT
    value: "databricks-gpt-5-2"
  - name: API_PROXY
    value: "${var.agent_url}"
  - name: LOG_SSE_EVENTS
    value: "true"
```

### Step 5.3: Build and Deploy

```bash
# Build the app
npm run build

# Deploy
databricks bundle deploy -t dev

# Start the app (if not auto-started)
databricks bundle run chatbot_ui -t dev
```

**Output:**
```
✓ App started successfully
URL: https://chatbot-user-3217006663075879.aws.databricksapps.com
```

### Step 5.4: Grant Service Principal Permission

The UI app's service principal needs permission to call the agent app:

```bash
# Get UI app's service principal
UI_APP_SP=$(databricks apps get chatbot-user --output json | jq -r '.service_principal_client_id')

# Get agent app name
AGENT_APP="dev-agent"

# Get auth token
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

# Grant CAN_USE permission
curl -X PUT "https://your-workspace.cloud.databricks.com/api/2.0/permissions/apps/${AGENT_APP}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"access_control_list\": [
      {
        \"service_principal_name\": \"${UI_APP_SP}\",
        \"permission_level\": \"CAN_USE\"
      }
    ]
  }"
```

**Why this is needed:**
- UI app runs with its own service principal
- Agent app requires authentication
- Service principal needs explicit `CAN_USE` permission
- Without this, you'll get 403 errors or HTML login pages

---

## Part 6: Testing and Verification

### Step 6.1: Test Deployed UI

```bash
# Get auth token
TOKEN=$(databricks auth token --host https://your-workspace.cloud.databricks.com --output json | jq -r '.access_token')

# Test /api/chat endpoint
curl -N "https://chatbot-user-3217006663075879.aws.databricksapps.com/api/chat" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "message": {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "role": "user",
      "parts": [{"type": "text", "text": "Hello"}]
    },
    "selectedChatModel": "chat-model",
    "selectedVisibilityType": "private"
  }'
```

**Expected:** SSE stream with `text-delta` events

### Step 6.2: Test in Browser

1. Open https://chatbot-user-3217006663075879.aws.databricksapps.com
2. Send message: "What is 2+2?"
3. Verify text appears **character-by-character** (streaming)
4. Check browser DevTools → Network → Look for SSE events

**Success criteria:**
- ✅ Text streams incrementally (not all at once)
- ✅ Multiple `text-delta` events in Network tab
- ✅ No JavaScript errors in Console
- ✅ Response completes with final text

### Step 6.3: Common Issues

If streaming doesn't work:

**1. No text appears, only lifecycle events**
- Check browser console for validation errors
- Verify event schema has `id` and `delta` fields
- See [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md)

**2. HTML login page instead of SSE**
- Workspace mismatch: UI and agent must be in same workspace
- Missing service principal permission (Step 5.4)
- Check logs: `databricks apps logs chatbot-user --follow`

**3. 403 Forbidden errors**
- Run Step 5.4 to grant permission
- Verify agent app name matches

**4. Connection timeout or hangs**
- Check agent app is running: `databricks apps get dev-agent`
- Test agent directly (Part 2, Step 2.3)
- Check backend is accessible from agent app

---

## Summary

You've now built a complete streaming chatbot with:

1. **✅ Backend** - FastAPI with OpenResponses API (`/v1/responses`)
2. **✅ Agent App** - FastAPI hosting YAML-defined agent (`/invocations`)
3. **✅ UI Server** - Express proxy converting formats
4. **✅ Browser UI** - React chat with streaming text
5. **✅ Deployed** - All components on Databricks Apps
6. **✅ Authenticated** - Service principal permissions configured
7. **✅ UI Template** - Using [OpenResponses PR branch](https://github.com/databricks/app-templates/compare/main...smurching:app-templates:feature/openresponses-support) for streaming support

**Architecture Flow:**
```
Browser (localhost:3000 dev, HTTPS prod)
  └─ POST /api/chat
       ↓
UI Server (Express on port 3001 dev, 8000 prod)
  └─ Calls callAgentApp() with OAuth token
       ↓
Agent App (FastAPI, POST /invocations)
  └─ DeclarativeAgent.from_yaml()
  └─ AgentRunner.run_streaming()
       ↓
Backend (FastAPI, POST /v1/responses)
  └─ LLM streaming
       ↓
OpenResponses SSE → UIMessageStream → Browser
```

**Key Differences from Generic Guides:**
- ✅ Uses DeclarativeAgent SDK, NOT manual LangChain setup
- ✅ Uses FastAPI, NOT Flask or MLflow wrappers
- ✅ Deploys directly with uvicorn, NOT MLflow serving
- ✅ YAML agent definitions, NOT Python agent classes

## Next Steps

- **Add tools** to your YAML agent (UC functions, code interpreter, vector search)
- **Enable tracing** for observability (see data_analyst.yaml example)
- **Add governance** (cost limits, rate limits, content safety)
- **Customize UI** (branding, layouts, custom tool renderers)
- **Production hardening** (error handling, retries, monitoring)

## References

- [Architecture Guide](ARCHITECTURE.md) - Complete system design
- [Streaming Debug Guide](STREAMING_DEBUG_GUIDE.md) - Troubleshooting SSE issues
- [Deployment Guide](../DEPLOYMENT_GUIDE.md) - Backend deployment details
- [SDK Documentation](../sdk/README.md) - DeclarativeAgent SDK API reference
- [Examples](../examples/) - Sample agents and usage patterns
