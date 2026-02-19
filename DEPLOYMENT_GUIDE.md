# Agent App Deployment Guide

This guide walks through deploying the agent app with the /invocations endpoint and testing the full stack.

## Overview

We've implemented the following:

1. ✅ **agent_app/main.py** - Updated with `/invocations` endpoint (OpenResponses-compatible)
2. ✅ **sdk/declarative_agent/runner.py** - Added `run_streaming()` method for SSE streaming
3. ✅ **databricks.yml** - Added `backend_app_url` variable
4. ✅ **Test suite** - Created contract tests for backend, agent app, and e2e flows

## Architecture

```
User/UI → Agent App (/invocations) → Backend App (/v1/responses) → LLM
```

## Deployment Steps

### Phase 1: Deploy Backend App (if not already deployed)

```bash
cd ~/declarative-agent

# Authenticate to Databricks
databricks auth login --host https://db-ml-models-dev-us-west.cloud.databricks.com

# Deploy backend app
databricks bundle deploy -t dev

# Get backend app details
databricks bundle summary -t dev | grep agent_backend

# Or list apps to find the backend
databricks apps list --output json | jq '.[] | select(.name | contains("backend"))'

# Get the backend app URL (save this for next step)
BACKEND_APP_ID="<id-from-above>"
BACKEND_APP_URL=$(databricks apps get $BACKEND_APP_ID | jq -r '.url')
echo "Backend URL: $BACKEND_APP_URL"
```

Expected output:
```
Backend URL: https://db-ml-models-dev-us-west.cloud.databricks.com/apps/xyz123
```

### Phase 2: Configure and Deploy Agent App

```bash
# Update databricks.yml with backend URL
# Edit the file and set the backend_app_url variable in the dev target:

# targets:
#   dev:
#     variables:
#       backend_app_url: "https://db-ml-models-dev-us-west.cloud.databricks.com/apps/xyz123"

# Or set it via command line
databricks bundle deploy -t dev --var="backend_app_url=$BACKEND_APP_URL"

# Get agent app details
AGENT_APP_ID=$(databricks apps list --output json | jq -r '.[] | select(.name | contains("data-analyst")) | .id')
AGENT_APP_URL=$(databricks apps get $AGENT_APP_ID | jq -r '.url')
echo "Agent App URL: $AGENT_APP_URL"
```

### Phase 3: Grant Permissions

The agent app needs permission to call the backend app.

```bash
# Get agent app service principal
AGENT_APP_SP=$(databricks apps get $AGENT_APP_ID | jq -r '.service_principal_name')
echo "Agent App SP: $AGENT_APP_SP"

# Grant CAN_USE permission on backend app
databricks apps update-permissions $BACKEND_APP_ID \
  --json "{
    \"add\": [
      {
        \"principal\": \"$AGENT_APP_SP\",
        \"permission\": \"CAN_USE\"
      }
    ]
  }"

# Verify permissions were granted
databricks apps get-permissions $BACKEND_APP_ID
```

Expected output should show the agent app service principal with CAN_USE permission.

### Phase 4: Test the Deployment

#### 4.1 Health Check

```bash
# Test backend health
curl "$BACKEND_APP_URL/health"

# Test agent app health
curl "$AGENT_APP_URL/health"
```

#### 4.2 Test /invocations endpoint

```bash
# Get OAuth token
TOKEN=$(databricks auth token)

# Test non-streaming mode
curl -X POST "$AGENT_APP_URL/invocations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "What is 2+2?"}],
    "stream": false,
    "databricks_options": {"user_id": 123}
  }' | jq

# Test streaming mode
curl -N -X POST "$AGENT_APP_URL/invocations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "What is 2+2?"}],
    "stream": true,
    "databricks_options": {"user_id": 123}
  }'
```

#### 4.3 Run Automated Tests

```bash
cd ~/declarative-agent

# Set environment variables
export BACKEND_APP_URL="$BACKEND_APP_URL"
export AGENT_APP_URL="$AGENT_APP_URL"

# Run backend contract tests
pytest tests/test_backend_contract.py -v

# Run agent app contract tests
pytest tests/test_agent_contract.py -v

# Run e2e integration tests
pytest tests/test_e2e_integration.py -v

# Run all tests
pytest tests/test_*contract.py tests/test_e2e_integration.py -v
```

Expected output:
```
tests/test_backend_contract.py::test_backend_streaming_contract PASSED
tests/test_backend_contract.py::test_backend_non_streaming_contract PASSED
tests/test_backend_contract.py::test_backend_conversation_history PASSED
tests/test_backend_contract.py::test_backend_background_mode PASSED
...
tests/test_agent_contract.py::test_agent_app_streaming_contract PASSED
tests/test_agent_contract.py::test_agent_app_non_streaming_contract PASSED
...
tests/test_e2e_integration.py::test_e2e_data_analyst_query PASSED
tests/test_e2e_integration.py::test_e2e_multi_turn_conversation PASSED
tests/test_e2e_integration.py::test_e2e_streaming_flow PASSED
```

## Verification Checklist

- [ ] Backend app is accessible and returns 200 OK on /health
- [ ] Agent app is accessible and returns 200 OK on /health
- [ ] Agent app service principal has CAN_USE permission on backend app
- [ ] /invocations endpoint returns 200 OK for non-streaming requests
- [ ] /invocations endpoint streams SSE events for streaming requests
- [ ] Multi-turn conversations preserve context (conversation_id works)
- [ ] Background mode returns task ID immediately
- [ ] All automated tests pass

## Troubleshooting

### Permission Errors (403 Forbidden)

If you get 403 errors when calling the backend from the agent app:

1. Verify the agent app service principal has CAN_USE permission:
   ```bash
   databricks apps get-permissions $BACKEND_APP_ID
   ```

2. Re-grant permissions if needed:
   ```bash
   databricks apps update-permissions $BACKEND_APP_ID \
     --json "{ \"add\": [{ \"principal\": \"$AGENT_APP_SP\", \"permission\": \"CAN_USE\" }] }"
   ```

### Backend URL Not Set

If agent app can't find backend, check the environment variable:

```bash
# Check app environment
databricks apps get $AGENT_APP_ID | jq '.config.env'

# Should show: BACKEND_APP_URL: "https://..."
```

If missing, redeploy with the variable:
```bash
databricks bundle deploy -t dev --var="backend_app_url=$BACKEND_APP_URL"
```

### SSE Streaming Not Working

If streaming returns complete response instead of SSE:

1. Check that request has `stream: true`
2. Verify Content-Type is `application/json`
3. Use `-N` flag with curl to disable buffering
4. Check backend logs for errors

### Tests Failing

If tests fail with authentication errors:

1. Re-authenticate:
   ```bash
   databricks auth login --host https://db-ml-models-dev-us-west.cloud.databricks.com
   ```

2. Verify token is valid:
   ```bash
   databricks auth token
   ```

If tests fail with connection errors:

1. Verify app URLs are correct:
   ```bash
   echo $BACKEND_APP_URL
   echo $AGENT_APP_URL
   ```

2. Test health endpoints directly:
   ```bash
   curl "$BACKEND_APP_URL/health"
   curl "$AGENT_APP_URL/health"
   ```

## Next Steps

After successful deployment:

1. **Document the architecture** - Update README with stack diagram
2. **Test with UI** - Deploy e2e-chatbot-app-next as a Databricks App
3. **Add monitoring** - Set up logging and metrics
4. **Production hardening** - Add rate limiting, better error handling
5. **Create more agents** - Use data_analyst.yaml as template

## Files Modified

### Core Implementation
- `agent_app/main.py` - Added /invocations endpoint with SSE streaming
- `sdk/declarative_agent/runner.py` - Added run_streaming() method
- `databricks.yml` - Added backend_app_url variable and agent app config
- `pyproject.toml` - Added httpx and pyyaml dependencies

### Tests
- `tests/test_backend_contract.py` - Backend API contract tests
- `tests/test_agent_contract.py` - Agent app contract tests
- `tests/test_e2e_integration.py` - End-to-end integration tests

## API Reference

### /invocations Endpoint

**Request:**
```json
{
  "input": [{"role": "user", "content": "What is 2+2?"}],
  "stream": true,
  "background": false,
  "databricks_options": {
    "user_id": 123,
    "conversation_id": "uuid-optional"
  }
}
```

**Response (non-streaming):**
```json
{
  "id": "resp_xyz",
  "output": [
    {
      "role": "assistant",
      "content": [{"type": "text", "text": "2+2 equals 4"}]
    }
  ],
  "conversation_id": "conv_abc"
}
```

**Response (streaming):**
```
data: {"type": "response.output_text.delta", "delta": "2+2"}
data: {"type": "response.output_text.delta", "delta": " equals"}
data: {"type": "response.output_text.delta", "delta": " 4"}
data: {"type": "response.output_item.done", "item": {...}}
data: [DONE]
```

**Response (background):**
```json
{
  "id": "task_xyz",
  "status": "in_progress",
  "conversation_id": "conv_abc"
}
```

## Support

For issues or questions:
- Check the troubleshooting section above
- Review backend logs: `databricks apps logs $BACKEND_APP_ID`
- Review agent app logs: `databricks apps logs $AGENT_APP_ID`
- Run health checks on both apps
- Verify permissions are set correctly
