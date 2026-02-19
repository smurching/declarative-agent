# Deployment Status - Agent App with /invocations Endpoint

## Summary

Successfully implemented Phase 1 (code changes) and partially completed Phase 2 (deployment). Both backend and agent apps are deployed and running, but there's a permission issue preventing agent-to-backend communication.

## ✅ Completed

### Phase 1: Code Implementation (100% Complete)

1. **agent_app/main.py** - Updated with `/invocations` endpoint
   - ✅ Renamed `/chat` → `/invocations`
   - ✅ Updated request model to `InvocationsRequest` (OpenResponses format)
   - ✅ Updated response model to `InvocationsResponse`
   - ✅ Added SSE streaming support with `StreamingResponse`
   - ✅ Support for streaming, non-streaming, and background modes
   - ✅ Extracts `user_id` and `conversation_id` from `databricks_options`

2. **sdk/declarative_agent/runner.py** - Added streaming method
   - ✅ Added `run_streaming()` method for SSE event streaming
   - ✅ Direct HTTP calls to backend `/v1/responses`
   - ✅ Fixed `/v1` prefix for Databricks Apps authentication

3. **Configuration Files**
   - ✅ databricks.yml - Added `backend_app_url` configuration
   - ✅ agent_app/requirements.txt - Created with all dependencies
   - ✅ agent_app/pyproject.toml - Created for package metadata
   - ✅ Copied SDK and examples into agent_app directory

4. **Bug Fixes**
   - ✅ Fixed syntax error in server/responses_handler.py (duplicate `else`)
   - ✅ Fixed agent app import paths for deployed environment
   - ✅ Fixed YAML file path in agent_app/main.py
   - ✅ Added `/v1` prefix to DatabricksOpenAI base_url

### Phase 2: Deployment (90% Complete)

1. **Backend App** - ✅ DEPLOYED & RUNNING
   - URL: https://dev-agent-backend-3217006663075879.aws.databricksapps.com
   - Status: Healthy
   - Health check: ✅ 200 OK

2. **Agent App** - ✅ DEPLOYED & RUNNING
   - URL: https://dev-data-analyst-3217006663075879.aws.databricksapps.com
   - Status: Healthy
   - Health check: ✅ 200 OK
   - Backend URL configured: ✅ Correct

### Phase 3: Automated Tests (100% Complete)

Test files created:
- ✅ tests/test_backend_contract.py
- ✅ tests/test_agent_contract.py
- ✅ tests/test_e2e_integration.py

## ⏳ Remaining Issue

### Permission Error (App-to-App Authentication)

**Current State:**
- Agent app can start and respond to health checks ✅
- Agent app has correct backend URL configured ✅
- Agent app correctly calls `/v1/responses` endpoint ✅
- **But:** Gets 401 Unauthorized when calling backend ❌

**Error Log:**
```
INFO:httpx:HTTP Request: POST https://dev-agent-backend-3217006663075879.aws.databricksapps.com/v1/responses "HTTP/1.1 401 Unauthorized"
ERROR:main:Error in /invocations endpoint: Error code: 401 - {}
openai.AuthenticationError: Error code: 401 - {}
```

**Root Cause:**
The agent app's service principal (`app-2sbfjd dev-data-analyst`) needs CAN_USE permission on the backend app, but standard permission grant commands aren't working.

**What We Tried:**
1. ✗ `databricks apps update-permissions` CLI command
2. ✗ Python SDK `w.apps.update_permissions()`
3. ✗ Adding backend as a resource in databricks.yml (not supported)

## 📋 Next Steps to Fix Permission Issue

### Option 1: Manual Permission Grant via Workspace UI

1. Go to Databricks workspace UI
2. Navigate to Apps → dev-agent-backend
3. Click "Permissions" tab
4. Add service principal: `app-2sbfjd dev-data-analyst`
5. Grant permission level: `CAN_USE`

### Option 2: Use Databricks API Directly

```python
from databricks.sdk import WorkspaceClient
import requests

w = WorkspaceClient()
token = w.config.token

# Get backend app permissions endpoint
backend_app_id = "f1db925f-33a9-4583-87b5-7167b44cf590"

# Update permissions via REST API
response = requests.patch(
    f"{w.config.host}/api/2.0/apps/{backend_app_id}/permissions",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "access_control_list": [
            {
                "user_name": "sid.murching@databricks.com",
                "permission_level": "CAN_MANAGE"
            },
            {
                "service_principal_name": "app-2sbfjd dev-data-analyst",
                "permission_level": "CAN_USE"
            }
        ]
    }
)
```

### Option 3: Modify Backend to Allow All Authenticated Users

Temporarily modify backend app to accept any authenticated Databricks user/service principal:

```python
# In server/main.py or responses_handler.py
# Add middleware to accept any authenticated request
# (Not recommended for production)
```

### Option 4: Use OAuth Token Pass-Through

Instead of service principal auth, pass the user's OAuth token from agent app to backend:

```python
# In agent_app/main.py
# Extract token from request header
# Pass it to AgentRunner for backend authentication
```

## Testing After Permission Fix

Once permissions are granted, run these tests:

### 1. Test /invocations Non-Streaming

```bash
python -c "
from databricks.sdk import WorkspaceClient
import requests

w = WorkspaceClient()
token = w.config.oauth_token().access_token

resp = requests.post(
    'https://dev-data-analyst-3217006663075879.aws.databricksapps.com/invocations',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={
        'input': [{'role': 'user', 'content': 'What is 2+2?'}],
        'stream': False,
        'databricks_options': {'user_id': 123}
    }
)
print(f'Status: {resp.status_code}')
print(resp.json())
"
```

### 2. Test /invocations Streaming

```bash
curl -N -X POST https://dev-data-analyst-3217006663075879.aws.databricksapps.com/invocations \
  -H "Authorization: Bearer $(databricks auth token --host https://db-ml-models-dev-us-west.cloud.databricks.com)" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Count to 5"}],
    "stream": true,
    "databricks_options": {"user_id": 123}
  }'
```

### 3. Run Automated Tests

```bash
export BACKEND_APP_URL="https://dev-agent-backend-3217006663075879.aws.databricksapps.com"
export AGENT_APP_URL="https://dev-data-analyst-3217006663075879.aws.databricksapps.com"

pytest tests/test_backend_contract.py tests/test_agent_contract.py tests/test_e2e_integration.py -v
```

## Architecture

```
User/Client
    ↓ OAuth Token
https://dev-data-analyst-3217006663075879.aws.databricksapps.com/invocations
    ↓ Service Principal: app-2sbfjd dev-data-analyst (NEEDS CAN_USE)
https://dev-agent-backend-3217006663075879.aws.databricksapps.com/v1/responses
    ↓ CAN_QUERY permission (already configured ✅)
databricks-gpt-5-2 (LLM)
```

## Files Changed

### Core Implementation
- `agent_app/main.py` - /invocations endpoint with SSE streaming
- `agent_app/sdk/declarative_agent/runner.py` - run_streaming() method + /v1 fix
- `server/responses_handler.py` - Fixed duplicate else syntax error
- `databricks.yml` - Backend URL configuration
- `agent_app/requirements.txt` - Dependencies
- `agent_app/pyproject.toml` - Package metadata

### Test Files (Created)
- `tests/test_backend_contract.py`
- `tests/test_agent_contract.py`
- `tests/test_e2e_integration.py`

### Documentation
- `DEPLOYMENT_GUIDE.md` - Complete deployment instructions
- `IMPLEMENTATION_SUMMARY.md` - Quick-start guide
- `DEPLOYMENT_STATUS.md` - This file

## Quick Commands Reference

```bash
# Check app status
databricks apps get dev-agent-backend
databricks apps get dev-data-analyst

# View logs
databricks apps logs dev-agent-backend | tail -50
databricks apps logs dev-data-analyst | tail -50

# Test health endpoints
python -c "
from databricks.sdk import WorkspaceClient
import requests
w = WorkspaceClient()
token = w.config.oauth_token().access_token
print('Backend:', requests.get('https://dev-agent-backend-3217006663075879.aws.databricksapps.com/health', headers={'Authorization': f'Bearer {token}'}).json())
print('Agent:', requests.get('https://dev-data-analyst-3217006663075879.aws.databricksapps.com/health', headers={'Authorization': f'Bearer {token}'}).json())
"

# Redeploy apps
databricks bundle deploy -t dev
databricks bundle run agent_backend -t dev
databricks bundle run data_analyst_agent -t dev
```

## Success Criteria

- [x] Backend app deployed and healthy
- [x] Agent app deployed and healthy
- [x] Agent app has correct backend URL
- [x] Agent app calls correct `/v1/responses` endpoint
- [ ] Agent app service principal has CAN_USE permission ⬅️ **BLOCKING**
- [ ] /invocations returns successful responses
- [ ] Streaming mode works
- [ ] Multi-turn conversations preserve context
- [ ] Automated tests pass

## Contact & Support

For permission issues, contact Databricks admin or workspace administrator to manually grant app-to-app permissions through the UI.
