# Test Client Setup - OpenAI Client Integration

## Overview

Tests use the actual OpenAI/Databricks OpenAI clients to ensure our backend is truly OpenResponses-compatible. The test framework automatically selects the appropriate client based on the target environment.

## Client Selection Logic

### Local Testing (Default)
```python
# Uses: openai.AsyncOpenAI
client = AsyncOpenAI(
    base_url="http://localhost:8000",
    api_key="",  # Empty string - no auth needed locally
)
```

**When:** Testing against local development server
**Auth:** None required
**How to trigger:** Run `pytest` normally (default behavior)

### Databricks Apps Testing
```python
# Uses: databricks_openai.AsyncDatabricksOpenAI
client = AsyncDatabricksOpenAI(
    base_url="https://your-workspace.cloud.databricks.com/apps/your-app",
    # Automatic Databricks OAuth authentication
)
```

**When:** Testing against deployed Databricks App
**Auth:** Automatic OAuth via Databricks SDK
**How to trigger:** Set `BASE_URL` environment variable

## Running Tests

### Test Locally (No Auth)

```bash
# Default - tests against http://localhost:8000
pytest

# Explicit local URL
BASE_URL=http://localhost:8000 pytest
```

**Requirements:**
- Local server running on port 8000
- No authentication needed

**Start local server:**
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### Test Deployed App (With Auth)

```bash
# Test against deployed Databricks App
BASE_URL=https://your-workspace.cloud.databricks.com/apps/your-app-name pytest
```

**Requirements:**
- Databricks App deployed and running
- Databricks CLI authenticated (`databricks auth login`)
- App URL accessible

**Get your app URL:**
```bash
databricks apps list
# Find your app's URL in the output
```

## Fixture Architecture

### Core Fixtures

#### `base_url` (str)
Returns the API base URL
- Default: `http://localhost:8000`
- Override: Set `BASE_URL` environment variable

#### `is_local` (bool)
Determines if testing locally vs deployed
- `True` if base_url contains "localhost" or "127.0.0.1"
- `False` otherwise (Databricks Apps)

#### `openai_base_client` (AsyncOpenAI | AsyncDatabricksOpenAI)
Returns the appropriate OpenAI client
- Local: `AsyncOpenAI` with empty API key
- Deployed: `AsyncDatabricksOpenAI` with auto-auth

#### `async_client` (httpx.AsyncClient)
Extracts the underlying httpx client from OpenAI client
- Maintains same auth configuration
- Used for making requests to `/responses` endpoint

## How Tests Use the Client

Tests receive `async_client` which is configured for the environment:

```python
@pytest.mark.asyncio
async def test_create_response(async_client: httpx.AsyncClient, sample_user_id):
    """Test creating a response."""
    payload = {
        "input": [{"role": "user", "content": "Hello"}],
        "databricks_options": {"user_id": sample_user_id}
    }

    # This request automatically includes auth if needed
    response = await async_client.post("/responses", json=payload)
    assert response.status_code == 200
```

## Authentication Details

### Local (No Auth)
- `AsyncOpenAI` with `api_key=""`
- No Authorization header
- Server accepts requests without authentication

### Databricks Apps (OAuth)
- `AsyncDatabricksOpenAI` handles auth automatically
- Fetches OAuth token via Databricks SDK
- Adds `Authorization: Bearer <token>` header
- Token refresh handled by client

## Environment Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `BASE_URL` | API endpoint | `http://localhost:8000` | `https://workspace.databricks.com/apps/agent-backend` |

## Troubleshooting

### Local Testing Issues

**Error: "Connection refused"**
```bash
# Check if server is running
curl http://localhost:8000/health

# Start server if needed
uvicorn server.main:app --port 8000
```

**Error: "422 Validation Error"**
- Check that payload matches OpenResponses spec
- Verify `databricks_options.user_id` is provided

### Deployed App Testing Issues

**Error: "401 Unauthorized"**
```bash
# Check Databricks authentication
databricks auth profiles

# Re-authenticate if needed
databricks auth login --host https://your-workspace.cloud.databricks.com
```

**Error: "404 Not Found"**
- Verify app is deployed: `databricks apps list`
- Check BASE_URL is correct
- Ensure app is running

**Error: "Timeout"**
- Deployed apps may be slower than local
- Increase timeout: `pytest --timeout=120`

## Example Test Runs

### Development Workflow

```bash
# 1. Start local server
uvicorn server.main:app --reload &

# 2. Run tests locally (fast feedback)
pytest -v

# 3. Deploy to staging
databricks bundle deploy --target dev

# 4. Test staging deployment
BASE_URL=$(databricks apps get agent-backend-dev --format json | jq -r '.url') pytest

# 5. Deploy to production
databricks bundle deploy --target prod

# 6. Test production (subset of tests)
BASE_URL=$(databricks apps get agent-backend-prod --format json | jq -r '.url') pytest tests/test_api_acceptance.py::TestHealthEndpoint
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
name: Test

on: [push, pull_request]

jobs:
  test-local:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Start server
        run: |
          pip install -e .
          uvicorn server.main:app &
          sleep 5
      - name: Run tests
        run: pytest -v

  test-deployed:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Configure Databricks
        run: |
          databricks auth login --host ${{ secrets.DATABRICKS_HOST }} --token ${{ secrets.DATABRICKS_TOKEN }}
      - name: Test deployed app
        env:
          BASE_URL: ${{ secrets.APP_URL }}
        run: pytest -v
```

## Benefits of This Approach

1. **Realistic Testing**: Uses actual OpenAI/Databricks clients that end users will use
2. **Automatic Auth**: No manual token management - clients handle it
3. **Environment Flexibility**: Same tests work locally and deployed
4. **API Compatibility**: Validates OpenResponses compatibility
5. **Easy Switching**: Single environment variable to test different environments

## Advanced Usage

### Test Specific Environment

```bash
# Local dev server
BASE_URL=http://localhost:8000 pytest

# Staging
BASE_URL=https://workspace.databricks.com/apps/agent-backend-dev pytest

# Production
BASE_URL=https://workspace.databricks.com/apps/agent-backend-prod pytest
```

### Custom Test Configuration

```python
# conftest.py - Add custom fixture
@pytest.fixture
def custom_client(base_url: str):
    """Custom client configuration."""
    if "staging" in base_url:
        # Special config for staging
        pass
    return client
```

### Debug Auth Issues

```python
# Add to test
def test_with_auth_debug(openai_base_client):
    """Debug authentication."""
    print(f"Client type: {type(openai_base_client)}")
    print(f"Base URL: {openai_base_client.base_url}")

    # Check if headers are set
    if hasattr(openai_base_client._client, 'headers'):
        print(f"Headers: {openai_base_client._client.headers}")
```

## Summary

The test framework automatically configures the appropriate OpenAI client based on your target environment:

- **Local:** Simple, no-auth testing with `AsyncOpenAI`
- **Deployed:** Authenticated testing with `AsyncDatabricksOpenAI`
- **Switching:** Just set `BASE_URL` environment variable

This ensures tests validate real-world usage patterns while maintaining flexibility across development, staging, and production environments.
