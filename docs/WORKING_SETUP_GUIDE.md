# Working Setup Guide: Full Stack with PR Branches

Complete end-to-end setup for testing the declarative agent with UI using all PR branches.

## Overview

This guide shows how to run the complete stack locally using the PR branches:
1. **Backend** (`/responses` API) - Port 8000
2. **Agent App** (wraps declarative agent) - Port 6000
3. **E2E Chatbot UI** (browser interface) - Ports 3000 (client) & 3001 (server)

## Architecture

```
Browser (localhost:3000)
  ↓
UI Server (localhost:3001)
  ↓ API_PROXY=http://localhost:6000/invocations
Agent App (localhost:6000)
  ↓ BACKEND_APP_URL=http://localhost:8000
Backend /responses API (localhost:8000)
  ↓
Databricks LLM
```

## Prerequisites

- Python 3.10+
- Node.js 20+
- Databricks CLI authenticated
- Access to Databricks LLM serving endpoint

## Step 1: Start the Backend (/responses API)

The backend provides the `/responses` endpoint that the agent calls.

```bash
cd ~/declarative-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
export DB_TYPE=sqlite
export DATABRICKS_CLI_PROFILE=your-profile
export WORKSPACE_ID=your-workspace-id

# Start backend
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

**Verify:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

## Step 2: Start the Agent App

The agent app wraps a declarative agent YAML and exposes `/invocations`.

```bash
cd ~/declarative-agent

# Start agent app
uvicorn agent_app.main:app --host 0.0.0.0 --port 6000 --reload
```

**Verify:**
```bash
curl http://localhost:6000/health
# Should return: {"status":"healthy","agent":"data_analyst","backend_url":"http://localhost:8000"}
```

## Step 3: Set Up E2E Chatbot UI (from PR branches)

### 3.1 Clone and Checkout PR Branch

```bash
# Clone app-templates fork
git clone https://github.com/smurching/app-templates.git
cd app-templates/e2e-chatbot-app-next
git checkout feature/openresponses-support
```

### 3.2 Install Dependencies with npm link

The chatbot app depends on `@databricks/ai-sdk-provider` with OpenResponses support.
For local testing, use `npm link`:

```bash
# First, set up the databricks-ai-bridge
cd ~/databricks-ai-bridge
git checkout feature/add-openresponses-support
cd integrations/ai-sdk-provider
npm install
npm run build
npm link

# Then, link it in the chatbot app
cd ~/app-templates/e2e-chatbot-app-next/packages/ai-sdk-providers
npm install
npm link @databricks/ai-sdk-provider

# Install root dependencies
cd ~/app-templates/e2e-chatbot-app-next
npm install
```

### 3.3 Configure Environment

Create `.env` in `~/app-templates/e2e-chatbot-app-next/`:

```bash
# Databricks Authentication
DATABRICKS_CONFIG_PROFILE=your-profile-name

# Point to local agent app
DATABRICKS_SERVING_ENDPOINT="databricks-gpt-5-2"  # For metadata only
API_PROXY="http://localhost:6000/invocations"

# Enable SSE event logging (optional)
LOG_SSE_EVENTS=true

# Database disabled for testing (ephemeral mode)
# Chat history will not persist across restarts
```

### 3.4 Start the Chatbot App

```bash
cd ~/app-templates/e2e-chatbot-app-next
npm run dev
```

This starts:
- **Client** on http://localhost:3000 (React app)
- **Server** on http://localhost:3001 (Express API)

**Verify:**
```bash
# Check server logs
tail -f /tmp/chatbot-app.log

# Should see:
# Backend server is running on http://localhost:3001
# Environment: development
```

## Step 4: Test the Full Stack

### Browser Test

1. Open http://localhost:3000
2. Type a message: "Hello!"
3. You should see:
   - Message sent to UI server (port 3001)
   - Server calls agent app (port 6000)
   - Agent app calls backend (port 8000)
   - Backend calls Databricks LLM
   - Response streams back through all layers

### curl Test

```bash
# Test agent app directly
curl -X POST http://localhost:6000/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

Expected output (SSE format):
```
data: {"type":"response.output_text.delta","delta":"Hello"}
data: {"type":"response.output_text.delta","delta":"!"}
data: {"type":"response.output_item.done","item":{"role":"assistant","content":"Hello!"}}
data: [DONE]
```

## Troubleshooting

### Port Already in Use

```bash
# Kill existing processes
lsof -ti:8000 | xargs kill  # Backend
lsof -ti:6000 | xargs kill  # Agent app
lsof -ti:3000,3001 | xargs kill  # Chatbot app
```

### Module Not Found: @databricks/ai-sdk-provider

```bash
# Re-link the package
cd ~/databricks-ai-bridge/integrations/ai-sdk-provider
npm link

cd ~/app-templates/e2e-chatbot-app-next/packages/ai-sdk-providers
npm link @databricks/ai-sdk-provider
```

### Agent App Can't Reach Backend

Check that `BACKEND_APP_URL` points to port 8000:
```bash
export BACKEND_APP_URL=http://localhost:8000
uvicorn agent_app.main:app --host 0.0.0.0 --port 6000 --reload
```

### UI Can't Reach Agent App

Check `.env` has correct `API_PROXY`:
```bash
API_PROXY="http://localhost:6000/invocations"
```

## Stack Status Checklist

Run these to verify all components:

```bash
# ✓ Backend running
curl -s http://localhost:8000/health | jq .

# ✓ Agent app running
curl -s http://localhost:6000/health | jq .

# ✓ UI server running
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/
# Should return: 404 (no route at /, but server is up)

# ✓ UI client running
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# Should return: 200
```

## PR References

This setup uses code from these PRs:

1. **databricks-ai-bridge #335** - OpenResponses language model
   https://github.com/databricks/databricks-ai-bridge/pull/335

2. **app-templates #125** - Use bridge OpenResponses support
   https://github.com/databricks/app-templates/pull/125

## Next Steps

Once you verify the local stack works:

1. **Test with Different Agents** - Modify `agent_app/examples/agents/data_analyst.yaml`
2. **Add Tools** - Add new tools to the backend or agent
3. **Deploy to Databricks** - Follow deployment guides to push to Databricks Apps
4. **Review PRs** - Provide feedback on the PRs

## File Locations

- Backend: `~/declarative-agent/server/`
- Agent App: `~/declarative-agent/agent_app/`
- Agent YAML: `~/declarative-agent/agent_app/examples/agents/data_analyst.yaml`
- UI Code: `~/app-templates/e2e-chatbot-app-next/`
- Bridge Code: `~/databricks-ai-bridge/integrations/ai-sdk-provider/`

---

**Last Updated:** February 19, 2026
**Status:** ✅ Fully working local stack
