# Complete Guide: Building and Deploying a Declarative Agent with UI

This guide walks through building a declarative agent from scratch and connecting it to a web UI with streaming responses.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Part 1: Build the Declarative Agent](#part-1-build-the-declarative-agent)
3. [Part 2: Deploy the Agent App](#part-2-deploy-the-agent-app)
4. [Part 3: Build the UI](#part-3-build-the-ui)
5. [Part 4: Configure Integration](#part-4-configure-integration)
6. [Part 5: Deploy the UI](#part-5-deploy-the-ui)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- **Databricks CLI** (>= 0.210.0): `brew install databricks`
- **Node.js** 20.x: `nvm install 20 && nvm use 20`
- **Python** 3.10+
- **jq**: `brew install jq`

### Databricks Workspace
- Access to a Databricks workspace
- Permissions to create apps
- Serving endpoint for LLM (or use Databricks Foundation Models)

### Authentication
```bash
databricks auth login --host https://your-workspace.cloud.databricks.com
```

Verify:
```bash
databricks auth profiles
```

---

## Part 1: Build the Declarative Agent

### Step 1.1: Create Agent Project Structure

```bash
mkdir my-agent
cd my-agent

# Create directory structure
mkdir -p agent_app server tests
```

### Step 1.2: Define Agent Configuration

Create `agent_app/agent.yaml`:

```yaml
agent_name: "my_agent"
description: "A helpful AI assistant"

system_prompt: |
  You are a helpful AI assistant. Answer questions clearly and concisely.

llm:
  model: "databricks-claude-sonnet-4"  # Or your serving endpoint name
  temperature: 0.7
  max_tokens: 1000

# Optional: Add tools
tools: []

# Optional: Add retrieval
retrieval: null
```

### Step 1.3: Create Agent Entry Point

Create `agent_app/main.py`:

```python
import os
import logging
from typing import Iterator, Any
from mlflow.deployments import get_deploy_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LangChain imports for agent logic
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import Runnable

def create_agent() -> Runnable:
    """Create and configure the agent."""
    from langchain_databricks import ChatDatabricks

    # Get LLM endpoint from config
    endpoint = os.environ.get("LLM_ENDPOINT", "databricks-claude-sonnet-4")

    # Create LLM client
    llm = ChatDatabricks(
        endpoint=endpoint,
        temperature=0.7,
        max_tokens=1000
    )

    # For simple agent, just return the LLM
    # For complex agents, use LangGraph or other frameworks
    return llm

def chat(messages: list[dict[str, str]]) -> Iterator[str]:
    """
    Process a chat request and yield response chunks.

    Args:
        messages: List of {role, content} dicts

    Yields:
        Text chunks from the LLM
    """
    try:
        agent = create_agent()

        # Convert messages to LangChain format
        lc_messages = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        # Stream response
        for chunk in agent.stream(lc_messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise

# MLflow model wrapper (if deploying via MLflow)
class AgentModel(mlflow.pyfunc.PythonModel):
    def predict(self, context, model_input):
        messages = model_input["messages"]
        return list(chat(messages))
```

### Step 1.4: Create Backend Server

Create `server/responses_handler.py`:

```python
"""
OpenResponses format handler.

Implements the Server-Sent Events (SSE) streaming format expected by
the UI integration.
"""
import json
import logging
from typing import Iterator, Any, Dict
from agent_app.main import chat

logger = logging.getLogger(__name__)

def generate_openresponses_stream(messages: list[dict]) -> Iterator[str]:
    """
    Generate OpenResponses SSE events from agent chat.

    Format:
        data: {"type":"response.output_text.delta","delta":"text"}
        data: {"type":"response.output_item.done","item":{...}}
        data: [DONE]
    """
    accumulated_text = []

    try:
        # Stream text deltas
        for chunk in chat(messages):
            if chunk:
                accumulated_text.append(chunk)
                event = {
                    "type": "response.output_text.delta",
                    "delta": chunk
                }
                yield f"data: {json.dumps(event)}\n\n"

        # Send completion event
        full_text = "".join(accumulated_text)
        done_event = {
            "type": "response.output_item.done",
            "item": {
                "role": "assistant",
                "content": full_text
            }
        }
        yield f"data: {json.dumps(done_event)}\n\n"

        # Send terminator
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in stream: {e}", exc_info=True)
        error_event = {
            "type": "response.error",
            "error": {
                "type": "internal_error",
                "message": str(e)
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"

def handle_responses_request(request_data: dict) -> Iterator[str]:
    """
    Main handler for /v1/responses endpoint.

    Args:
        request_data: {
            "messages": [...],
            "config": {...}
        }

    Returns:
        Iterator of SSE formatted strings
    """
    messages = request_data.get("messages", [])

    # Convert to simple format expected by agent
    simple_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        # Handle different content formats
        if isinstance(content, list):
            # Extract text from parts
            text_parts = [
                part.get("text", "")
                for part in content
                if part.get("type") == "text"
            ]
            content = " ".join(text_parts)

        simple_messages.append({
            "role": role,
            "content": content
        })

    return generate_openresponses_stream(simple_messages)
```

Create `server/app.py`:

```python
"""
Flask/FastAPI server for the agent backend.
"""
from flask import Flask, request, Response, stream_with_context
from server.responses_handler import handle_responses_request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/v1/responses', methods=['POST'])
def responses():
    """Handle OpenResponses streaming requests."""
    try:
        request_data = request.get_json()

        def generate():
            try:
                for chunk in handle_responses_request(request_data):
                    yield chunk
            except Exception as e:
                logger.error(f"Error in generate: {e}", exc_info=True)
                raise

        return Response(
            stream_with_context(generate()),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    except Exception as e:
        logger.error(f"Error in responses endpoint: {e}", exc_info=True)
        return {"error": str(e)}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

### Step 1.5: Create Requirements

Create `requirements.txt`:

```
# LangChain and agent dependencies
langchain>=0.1.0
langchain-core>=0.1.0
langchain-databricks>=0.1.0

# MLflow for deployment
mlflow>=2.10.0

# Server
flask>=3.0.0

# Utilities
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### Step 1.6: Create Agent Wrapper

Create `agent_app/mlflow_wrapper.py`:

```python
"""
MLflow wrapper for deploying the agent.
"""
import mlflow
from agent_app.main import chat

class AgentWrapper(mlflow.pyfunc.PythonModel):
    """
    MLflow PyFunc wrapper for the agent.

    Input format:
        {
            "input": [
                {"role": "user", "content": "Hello"}
            ],
            "stream": true
        }

    Output:
        Iterator of text chunks (if stream=true)
        or full response (if stream=false)
    """

    def predict(self, context, model_input):
        """Handle prediction requests."""
        messages = model_input.get("input", [])
        stream = model_input.get("stream", False)

        if stream:
            # Return generator for streaming
            return chat(messages)
        else:
            # Collect all chunks
            chunks = list(chat(messages))
            return {"output": "".join(chunks)}
```

---

## Part 2: Deploy the Agent App

### Step 2.1: Create Databricks Asset Bundle

Create `databricks.yml`:

```yaml
bundle:
  name: my-agent

variables:
  agent_name:
    default: "my-agent-${workspace.current_user.short_name}"

resources:
  apps:
    my_agent_app:
      name: ${var.agent_name}
      description: "My declarative agent"

      # Source code
      src: .

      # Resources needed
      resources:
        - name: llm-endpoint
          serving_endpoint:
            name: "databricks-claude-sonnet-4"
            permission: CAN_QUERY

      # Runtime configuration
      config:
        command: ["python", "-m", "server.app"]
        env:
          - name: LLM_ENDPOINT
            value: "databricks-claude-sonnet-4"

targets:
  dev:
    mode: development
    workspace:
      host: https://your-workspace.cloud.databricks.com
```

### Step 2.2: Deploy Agent

```bash
# Validate configuration
databricks bundle validate

# Deploy
databricks bundle deploy -t dev

# The output will show the app URL
# Example: https://my-agent-user-1234567890.aws.databricksapps.com
```

### Step 2.3: Test Agent Directly

```bash
# Get your auth token
TOKEN=$(databricks auth token --host https://your-workspace.cloud.databricks.com --output json | jq -r '.access_token')

# Test the agent
curl -N "https://my-agent-user-1234567890.aws.databricksapps.com/invocations" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {"role": "user", "content": "Hello"}
    ],
    "stream": true
  }'
```

**Expected output:**
```
data: {"type":"response.output_text.delta","delta":"Hello"}
data: {"type":"response.output_text.delta","delta":"!"}
data: {"type":"response.output_text.delta","delta":" How"}
...
data: [DONE]
```

---

## Part 3: Build the UI

### Step 3.1: Clone UI Template

```bash
# Clone the e2e-chatbot-app template
git clone https://github.com/databricks/e2e-chatbot-app-next.git my-ui
cd my-ui
```

### Step 3.2: Install Dependencies

```bash
npm install
```

### Step 3.3: Configure Environment

Create `.env`:

```bash
# Databricks Authentication
DATABRICKS_CONFIG_PROFILE=your-profile-name

# Agent App URL (from Step 2.2)
API_PROXY="https://my-agent-user-1234567890.aws.databricksapps.com/invocations"

# LLM Endpoint (for metadata only)
DATABRICKS_SERVING_ENDPOINT="databricks-claude-sonnet-4"

# Optional: Enable logging
LOG_SSE_EVENTS=true
```

### Step 3.4: Test Locally

```bash
# Start dev servers (client on 3000, server on 3001)
npm run dev

# In another terminal, test
npx tsx tests/test_ui_streaming_debug.ts
```

**Expected output:**
```
✓ Got response, reading stream...
[Event 1] start
[Event 2] text-start
[Event 3] text-delta
  └─ Text: "Hello"
...
✅ SUCCESS: Received streaming text content!
```

---

## Part 4: Configure Integration

### Step 4.1: Update Server to Call Agent

The UI template already includes agent integration in `server/src/routes/chat.ts`. Verify it's configured:

```typescript
// In chat.ts
if (isAgentApp) {
  // Direct agent app integration
  const agentToken = await getDatabricksToken();

  const agentResponse = await callAgentApp({
    url: process.env.API_PROXY!,
    messages: uiMessages,
    conversationId: id,
    userId: session.user.email ?? session.user.id,
    token: agentToken,
  });

  // Parse and stream to browser
  const textPartId = generateUUID();

  writer.write({
    type: 'text-start',
    id: textPartId,
  });

  for await (const textDelta of parseOpenResponsesStream(agentResponse)) {
    writer.write({
      type: 'text-delta',
      id: textPartId,
      delta: textDelta,
    });
  }
}
```

### Step 4.2: Verify Agent Client

Check `packages/core/src/agent-client.ts` has proper parsing:

```typescript
export async function* parseOpenResponsesStream(
  response: Response
): AsyncGenerator<string> {
  if (!response.body) {
    throw new Error('Response has no body');
  }

  const reader = response.body.getReader();
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

      try {
        const event = JSON.parse(data);

        // Extract text from OpenResponses format
        if (event.type === 'response.output_text.delta' && event.delta) {
          yield event.delta;
        } else if (event.type === 'response.error') {
          throw new Error(event.error?.message || 'Agent app error');
        }
      } catch (e) {
        if (!(e instanceof SyntaxError)) throw e;
      }
    }
  }
}
```

---

## Part 5: Deploy the UI

### Step 5.1: Configure Databricks Bundle

Update `databricks.yml`:

```yaml
bundle:
  name: my-chatbot-ui

variables:
  app_name:
    default: "my-chatbot-${workspace.current_user.short_name}"

  agent_url:
    default: "https://my-agent-user-1234567890.aws.databricksapps.com/invocations"

resources:
  apps:
    chatbot_ui:
      name: ${var.app_name}
      description: "Chat UI for my agent"

      src: .

      # Grant UI app permission to call agent app
      resources:
        - name: agent
          serving_endpoint:
            name: databricks-claude-sonnet-4  # For metadata
            permission: CAN_QUERY

        # Important: Grant permission to agent app
        - name: agent-app
          app:
            name: my-agent-user  # Your agent app name
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
    value: "databricks-claude-sonnet-4"
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

# Start the app
databricks bundle run chatbot_ui -t dev
```

**Output:**
```
✓ App started successfully
You can access the app at https://my-chatbot-user-3217006663075879.aws.databricksapps.com
```

### Step 5.4: Grant Service Principal Permission

```bash
# Get UI app's service principal
UI_APP_SP=$(databricks apps get my-chatbot-user --output json | jq -r '.service_principal_client_id')

# Get agent app name
AGENT_APP="my-agent-user"

# Grant permission
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

curl -X PUT "https://your-workspace.cloud.databricks.com/api/2.0/permissions/apps/${AGENT_APP}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"access_control_list\": [
      {
        \"service_principal_name\": \"${UI_APP_SP}\",
        \"permission_level\": \"CAN_USE\"
      },
      {
        \"user_name\": \"your.email@company.com\",
        \"permission_level\": \"CAN_MANAGE\"
      }
    ]
  }"
```

---

## Testing

### Test 1: Browser UI

1. Open: `https://my-chatbot-user-3217006663075879.aws.databricksapps.com`
2. Log in with your Databricks credentials
3. Send message: "Hello"
4. Verify text streams in character-by-character

### Test 2: curl API Endpoint

```bash
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

curl -N "https://my-chatbot-user-3217006663075879.aws.databricksapps.com/api/chat" \
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

**Expected:**
```
data: {"type":"text-start","id":"..."}
data: {"type":"text-delta","id":"...","delta":"Hello"}
...
data: [DONE]
```

### Test 3: Check Logs

```bash
# Agent app logs
databricks apps logs my-agent-user --follow

# UI app logs
databricks apps logs my-chatbot-user --follow
```

---

## Troubleshooting

### Issue: "Received HTML login page"

**Cause:** Authentication failure

**Fix:**
1. Check workspace matches: `.env` profile vs agent URL
2. Verify service principal permission
3. Check token expiry

```bash
# Verify profile
databricks auth profiles

# Test token
databricks auth token --output json
```

### Issue: "Type validation failed: unrecognized keys"

**Cause:** Wrong event field names

**Fix:** In `chat.ts`, use `delta` not `textDelta`:
```typescript
writer.write({
  type: 'text-delta',
  id: textPartId,
  delta: textDelta,  // ← Correct field name
});
```

### Issue: "Cannot set headers after they are sent"

**Cause:** Manually setting headers before AI SDK

**Fix:** Remove any manual `res.setHeader()` calls before `pipeUIMessageStreamToResponse()`

### Issue: Browser shows lifecycle events but no text

**Cause:** JavaScript validation errors

**Fix:**
1. Check browser console for errors
2. Hard refresh (CMD+SHIFT+R)
3. Verify `text-start` has `id` field
4. Verify `text-delta` events have matching `id`

### Issue: "Invalid UUID" error

**Cause:** UUID doesn't match v4 format

**Fix:** Use proper v4 UUIDs with correct variant bits:
```bash
# Valid format: xxxxxxxx-xxxx-4xxx-[89ab]xxx-xxxxxxxxxxxx
# Third segment starts with 4 (version)
# Fourth segment starts with 8, 9, a, or b (variant)
```

---

## Best Practices

### 1. Logging

Add comprehensive logging:

```python
# Agent
logger.info(f"Processing message: {message[:50]}...")
logger.info(f"Generated response chunk: {chunk}")
```

```typescript
// UI Server
console.log('[AgentClient] Event:', event.type);
console.log('[Chat] Text chunk:', textDelta);
```

### 2. Error Handling

Always catch and report errors:

```typescript
try {
  for await (const textDelta of parseOpenResponsesStream(agentResponse)) {
    writer.write({ type: 'text-delta', id: textPartId, delta: textDelta });
  }
} catch (error) {
  console.error('[Chat] Streaming error:', error);
  writer.write({ type: 'data-error', data: error.message });
}
```

### 3. Testing

Test at each integration point:

```bash
# 1. Test agent backend directly
curl http://localhost:8000/v1/responses ...

# 2. Test agent app endpoint
curl https://my-agent.../invocations ...

# 3. Test UI server locally
npm run dev

# 4. Test deployed UI
curl https://my-chatbot.../api/chat ...
```

### 4. Monitoring

Monitor in production:

```bash
# Check app status
databricks apps get my-chatbot-user

# Stream logs
databricks apps logs my-chatbot-user --follow

# Check metrics (if configured)
databricks apps metrics my-chatbot-user
```

### 5. Security

- Use service principals for app-to-app auth
- Grant minimal permissions (CAN_USE, not CAN_MANAGE)
- Don't log sensitive data (tokens, PII)
- Validate all user input with Zod schemas

---

## Summary

You've now built and deployed a complete streaming chatbot system:

1. ✅ Created a declarative agent with OpenResponses streaming
2. ✅ Deployed agent as Databricks App
3. ✅ Built web UI with React + Express
4. ✅ Integrated UI with agent via SSE streaming
5. ✅ Deployed UI as Databricks App
6. ✅ Configured authentication and permissions
7. ✅ Tested end-to-end with curl and browser

**Architecture:**
```
Browser → UI App → Agent App → LLM
  (React)  (Express)  (Python)  (Databricks)
```

**Key Technologies:**
- Databricks Apps (deployment platform)
- OpenResponses (streaming format)
- Vercel AI SDK (React streaming)
- Server-Sent Events (transport)

For more details, see [ARCHITECTURE.md](./ARCHITECTURE.md).
