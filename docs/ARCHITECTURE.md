# Streaming Chatbot Architecture

## Overview

This document describes the architecture for integrating a Databricks declarative agent app with a browser-based UI, focusing on how Server-Sent Events (SSE) streaming works end-to-end.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Browser (React/Vite)                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Chat Component (chat.tsx)                                       │  │
│  │    - useChat() from @ai-sdk/react                               │  │
│  │    - ChatTransport (custom)                                     │  │
│  │    - Sends POST to /api/chat                                    │  │
│  │    - Receives SSE stream                                        │  │
│  │    - Renders streaming text                                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP POST /api/chat
                             │ Accept: text/event-stream
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     UI Server (Express/Node.js)                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Chat Route (server/src/routes/chat.ts)                         │  │
│  │    1. Receives chat request                                     │  │
│  │    2. Calls callAgentApp() with OAuth token                     │  │
│  │    3. Parses OpenResponses SSE stream                           │  │
│  │    4. Converts to UIMessageStream format                        │  │
│  │    5. Sends to browser via pipeUIMessageStreamToResponse()      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Agent Client (packages/core/src/agent-client.ts)               │  │
│  │    - callAgentApp(): POST to agent /invocations                 │  │
│  │    - parseOpenResponsesStream(): Parse SSE events               │  │
│  │    - Yields text deltas                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP POST /invocations
                             │ Authorization: Bearer <token>
                             │ {input: [...], stream: true}
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Agent App (Python/MLflow)                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Main Handler (declarative-agent/agent_app/main.py)             │  │
│  │    1. Receives request                                          │  │
│  │    2. Validates authentication                                  │  │
│  │    3. Calls backend /v1/responses                              │  │
│  │    4. Streams OpenResponses SSE events                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP POST /v1/responses
                             │ OpenResponses format
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Backend (LangGraph/Agent Logic)                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Responses Handler (declarative-agent/server/responses_handler) │  │
│  │    1. Executes agent logic                                      │  │
│  │    2. Calls LLM for text generation                            │  │
│  │    3. Yields OpenResponses events:                              │  │
│  │       - response.output_text.delta                              │  │
│  │       - response.output_item.done                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Browser → UI Server

**Request:**
```json
POST /api/chat
Content-Type: application/json

{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "message": {
    "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "role": "user",
    "parts": [{"type": "text", "text": "What is 2+2?"}]
  },
  "selectedChatModel": "chat-model",
  "selectedVisibilityType": "private"
}
```

### 2. UI Server → Agent App

**Request:**
```json
POST /invocations
Authorization: Bearer <token>
Content-Type: application/json

{
  "input": [
    {
      "role": "user",
      "content": "What is 2+2?"
    }
  ],
  "stream": true
}
```

### 3. Agent App → Backend

**Request:**
```json
POST /v1/responses
Content-Type: application/json

{
  "messages": [...],
  "config": {...}
}
```

**Response (SSE):**
```
data: {"type":"response.output_text.delta","delta":"2"}

data: {"type":"response.output_text.delta","delta":" +"}

data: {"type":"response.output_text.delta","delta":" "}

data: {"type":"response.output_text.delta","delta":"2"}

data: {"type":"response.output_text.delta","delta":" ="}

data: {"type":"response.output_text.delta","delta":" "}

data: {"type":"response.output_text.delta","delta":"4"}

data: {"type":"response.output_text.delta","delta":"."}

data: {"type":"response.output_item.done","item":{"role":"assistant","content":"2 + 2 = 4."}}

data: [DONE]
```

### 4. UI Server Processing

The UI server converts OpenResponses format to UIMessageStream format:

**Input (from agent):**
```json
{"type":"response.output_text.delta","delta":"2"}
```

**Output (to browser):**
```json
{"type":"text-delta","id":"ce21166c-a9c2-4a8c-9356-2ae28bacb19e","delta":"2"}
```

**Key transformations:**
1. Add `text-start` event with unique `id` before first text-delta
2. Add same `id` to all `text-delta` events (required by Vercel AI SDK)
3. Change field name from OpenResponses format to UIMessageStream format

### 5. Browser → UI Rendering

The browser's `useChat` hook processes the SSE stream and updates React state, causing the UI to re-render with each text chunk.

## Critical Implementation Details

### 1. Event Schema Validation

The Vercel AI SDK strictly validates event schemas. For `text-delta` events:

**✅ Correct:**
```typescript
writer.write({
  type: 'text-delta',
  id: textPartId,      // Required!
  delta: textDelta,    // Must be 'delta', NOT 'textDelta'
});
```

**❌ Incorrect:**
```typescript
writer.write({
  type: 'text-delta',
  textDelta: textDelta,  // Wrong field name - causes validation error
});
```

**❌ Also Incorrect:**
```typescript
writer.write({
  type: 'text-delta',
  delta: textDelta,
  // Missing 'id' field - causes "missing text part" error
});
```

### 2. Text-Start Requirement

The AI SDK requires a `text-start` event before any `text-delta` events:

```typescript
// Generate ID for the text part
const textPartId = generateUUID();

// Send text-start with ID
writer.write({
  type: 'text-start',
  id: textPartId,
});

// Then send text-delta events with same ID
for await (const textDelta of parseOpenResponsesStream(agentResponse)) {
  writer.write({
    type: 'text-delta',
    id: textPartId,
    delta: textDelta,
  });
}
```

### 3. Headers and Buffering

**DO NOT** manually set SSE headers before `pipeUIMessageStreamToResponse()`:

**❌ Don't do this:**
```typescript
res.setHeader('Content-Type', 'text/event-stream');
res.flushHeaders();
pipeUIMessageStreamToResponse({ stream, response: res });
// Error: Cannot set headers after they are sent
```

**✅ Let the AI SDK handle it:**
```typescript
pipeUIMessageStreamToResponse({ stream, response: res });
// SDK sets all required headers
```

### 4. Authentication Flow

**Local Development:**
- UI Server uses CLI auth (`DATABRICKS_CONFIG_PROFILE`)
- Gets user token from `~/.databrickscfg`
- Forwards token to agent app

**Production (Databricks Apps):**
- UI Server uses service principal OAuth
- Gets token via `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`
- Agent app must have `CAN_USE` permission for UI app's service principal

**Granting Permission:**
```bash
# Get UI app's service principal ID
UI_APP_SP=$(databricks apps get db-chatbot-dev-<user> --output json | jq -r '.service_principal_client_id')

# Grant CAN_USE permission on agent app
databricks auth token --output json | jq -r '.access_token' > /tmp/token.txt
TOKEN=$(cat /tmp/token.txt)

curl -X PUT "https://<workspace>/api/2.0/permissions/apps/<agent-app-name>" \
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

rm /tmp/token.txt
```

### 5. Workspace Matching

**Critical:** The UI server and agent app must be in the **same Databricks workspace**.

**Check your configuration:**
```bash
# .env file should point to same workspace as agent app URL
DATABRICKS_CONFIG_PROFILE=db-ml-models-dev-us-west  # Correct workspace

# Agent app URL
API_PROXY="https://dev-data-analyst-3217006663075879.aws.databricksapps.com/invocations"
```

**Common mistake:** UI server authenticating to `e2-dogfood` while agent app is in `db-ml-models-dev-us-west`. Tokens from one workspace don't work in another!

## Port Configuration

### Local Development
- **Client (Vite):** Port 3000
- **Server (Express):** Port 3001
- **Proxy:** Client proxies `/api` requests to server

### Production (Databricks Apps)
- **App listens on:** Port 8000 (set by `PORT` env var)
- **External access:** HTTPS URL from Databricks Apps

The server automatically detects the port:
```typescript
const PORT = process.env.CHAT_APP_PORT || process.env.PORT || (isDevelopment ? 3001 : 3000);
```

## Common Issues and Solutions

### Issue 1: "ERR_UNSAFE_PORT" in Browser

**Cause:** Trying to use port 6000 (reserved for X11)

**Solution:** Use safe ports like 3000, 5173, 8080, etc.

### Issue 2: "Cannot set headers after they are sent"

**Cause:** Manually setting headers before AI SDK tries to set them

**Solution:** Remove manual header setting, let `pipeUIMessageStreamToResponse` handle it

### Issue 3: "Received text-delta for missing text part"

**Cause:** Missing `text-start` event or mismatched IDs

**Solution:** Always send `text-start` with ID before any `text-delta` events

### Issue 4: "Type validation failed: unrecognized keys [textDelta]"

**Cause:** Using wrong field name in event

**Solution:** Use `delta`, not `textDelta`

### Issue 5: HTML Login Page Instead of SSE

**Cause:** Authentication failure or workspace mismatch

**Solution:**
1. Check `DATABRICKS_CONFIG_PROFILE` matches agent app workspace
2. Verify service principal has `CAN_USE` permission
3. Check token isn't expired

### Issue 6: Browser Receives Events But No Text

**Cause:** JavaScript validation errors in browser console

**Solution:**
1. Check browser console for errors
2. Hard refresh (CMD+SHIFT+R) to clear cached JS
3. Verify event schema matches AI SDK expectations

## Testing

### Local Testing
```bash
# Terminal 1: Start dev servers
npm run dev

# Terminal 2: Test endpoint
npx tsx tests/test_ui_streaming_debug.ts
```

### Production Testing
```bash
# Deploy
databricks bundle deploy -t dev
databricks bundle run databricks_chatbot -t dev

# Test with curl
TOKEN=$(databricks auth token --host <workspace-url> --output json | jq -r '.access_token')

curl -N "https://<app-url>/api/chat" \
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

**Note:** UUIDs must be valid v4 format (third segment starts with 1-8, fourth segment starts with [89abAB])

## Performance Considerations

### Latency Sources
1. **Network roundtrip** to agent app (~50-200ms)
2. **LLM first token** (~500-2000ms depending on model)
3. **Token generation** (~50-100ms per token)
4. **SSE parsing overhead** (~1-5ms per event)

### Optimization Tips
1. Use faster LLM models for lower latency
2. Keep agent app and UI app in same region
3. Use HTTP/2 for connection reuse
4. Minimize network hops

## Debugging Tips

### Enable Detailed Logging

**UI Server:**
```typescript
// In agent-client.ts
console.log('[AgentClient] Event:', event);
console.log('[AgentClient] Delta:', event.delta);
```

**Agent App:**
```python
# In main.py
logger.info(f"Received request: {request_dict}")
logger.info(f"Streaming response: {event}")
```

### Check Server Logs
```bash
# Local
tail -f /private/tmp/claude-502/-Users-sid-murching/tasks/<task-id>.output

# Production
databricks apps logs db-chatbot-dev-<user> --follow
```

### Inspect Network Traffic

**Browser DevTools:**
1. Network tab → Filter by "chat"
2. Click request → Response tab
3. Look for raw SSE events (data: {...})

**Check for:**
- All lifecycle events present
- Text-delta events contain text
- [DONE] marker at end
- No HTML error pages

## Security Considerations

1. **Token Handling:** Never log full tokens, use `hasToken: !!token`
2. **CORS:** Restrict origins in production
3. **Rate Limiting:** Consider adding rate limits for /api/chat
4. **Input Validation:** All user input is validated with Zod schemas
5. **Service Principal Permissions:** Grant minimal required permissions

## Further Reading

- [Vercel AI SDK Documentation](https://sdk.vercel.ai/docs)
- [Databricks Apps Documentation](https://docs.databricks.com/apps/)
- [OpenResponses Format Spec](https://github.com/databricks/openresponses)
- [Server-Sent Events MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
