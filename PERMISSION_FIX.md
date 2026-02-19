# Quick Fix: Grant App-to-App Permission

The automated permission grant via API isn't working due to Databricks Apps permission model limitations. Here's how to fix it manually:

## Option 1: Via Databricks UI (Recommended - 2 minutes)

1. Open your Databricks workspace: https://db-ml-models-dev-us-west.cloud.databricks.com
2. Navigate to **Apps** in the left sidebar
3. Find and click on **dev-agent-backend**
4. Click the **Permissions** tab
5. Click **Grant** or **Add** button
6. In the "Principal" field, enter: `app-2sbfjd dev-data-analyst`
7. Select permission level: **CAN_USE**
8. Click **Add** or **Save**

## Option 2: Try Alternative API Endpoint

If the UI doesn't work, try this Python script:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Try using the set_permissions method directly
try:
    from databricks.sdk.service.apps import AppPermissions, AppAccessControlRequest, AppPermissionLevel

    permissions = AppPermissions(
        access_control_list=[
            AppAccessControlRequest(
                user_name='sid.murching@databricks.com',
                permission_level=AppPermissionLevel.CAN_MANAGE
            ),
            AppAccessControlRequest(
                service_principal_name='app-2sbfjd dev-data-analyst',
                permission_level=AppPermissionLevel.CAN_USE
            )
        ]
    )

    # Use set_permissions instead of update_permissions
    w.apps.set_permissions(
        app_name='dev-agent-backend',
        access_control_list=permissions.access_control_list
    )

    print('✓ Permissions set successfully')
except Exception as e:
    print(f'Error: {e}')
```

## Option 3: Temporary Workaround - Disable Auth

As a temporary workaround for testing, you can modify the backend to accept all authenticated requests:

```python
# In server/main.py, add this middleware:
from fastapi import Request

@app.middleware("http")
async def allow_all_authenticated(request: Request, call_next):
    # Skip auth checks for now
    response = await call_next(request)
    return response
```

Then redeploy backend: `databricks bundle deploy -t dev && databricks bundle run agent_backend -t dev`

## Verify It Works

After granting permission, test with:

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
if resp.status_code == 200:
    print('✓ SUCCESS!')
    print(resp.json())
else:
    print(f'Error: {resp.text}')
"
```

Expected output:
```
Status: 200
✓ SUCCESS!
{'id': 'resp_...', 'output': [...], 'conversation_id': 'conv_...'}
```

## Why This Is Needed

The agent app needs permission to call the backend app. Without this:
- Agent app: `app-2sbfjd dev-data-analyst`
- Tries to call: `dev-agent-backend`
- Gets: 401 Unauthorized ❌

With CAN_USE permission:
- Agent app: `app-2sbfjd dev-data-analyst`
- Calls: `dev-agent-backend`
- Returns: 200 OK ✅

Once this permission is granted, the full stack will work end-to-end!
