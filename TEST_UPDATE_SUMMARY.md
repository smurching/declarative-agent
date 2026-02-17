# Test Suite Update - OpenAI Client Integration

## What Changed

The test suite has been updated to use the actual **OpenAI** and **Databricks OpenAI** clients instead of raw httpx, ensuring tests validate real-world usage patterns.

## Key Changes

### 1. Client Selection Logic

**Before:**
```python
# Raw httpx.AsyncClient with manual auth handling
async_client = httpx.AsyncClient(base_url=base_url, headers=headers)
```

**After:**
```python
# Local testing: openai.AsyncOpenAI
client = AsyncOpenAI(base_url="http://localhost:8000", api_key="")

# Deployed testing: databricks_openai.AsyncDatabricksOpenAI
client = AsyncDatabricksOpenAI(base_url="https://workspace.../apps/...")
```

### 2. Authentication Handling

| Scenario | Client | Auth Method |
|----------|--------|-------------|
| **Local** | `AsyncOpenAI` | Empty API key - no auth needed |
| **Deployed** | `AsyncDatabricksOpenAI` | Automatic OAuth via Databricks SDK |

### 3. Environment-Based Testing

```bash
# Test locally (default)
pytest

# Test deployed app
BASE_URL=https://your-workspace.../apps/your-app pytest
```

## Updated Files

### Core Changes

1. **`tests/conftest.py`**
   - Added `openai_base_client` fixture (selects AsyncOpenAI or AsyncDatabricksOpenAI)
   - Added `base_url` fixture (default: http://localhost:8000)
   - Added `is_local` fixture (determines local vs deployed)
   - Updated `async_client` to extract httpx client from OpenAI client
   - Removed manual auth token handling (now automatic)

2. **`pyproject.toml`**
   - Added `openai>=1.0.0` to dev dependencies

### Documentation Updates

3. **`tests/TEST_CLIENT_SETUP.md`** (NEW)
   - Complete guide to OpenAI client integration
   - Authentication details
   - Environment variable configuration
   - Troubleshooting guide
   - Examples for local and deployed testing

4. **`TEST_SUMMARY.md`** (UPDATED)
   - Updated fixtures documentation
   - Added environment variable instructions
   - Updated running tests section

5. **`TESTING_QUICKSTART.md`** (UPDATED)
   - Added local vs deployed testing instructions
   - Updated with BASE_URL environment variable usage

## Benefits

### 1. Realistic Testing
✅ Uses the same clients that end users will use
✅ Validates true OpenResponses API compatibility
✅ Tests actual authentication flows

### 2. Automatic Authentication
✅ No manual token management needed
✅ DatabricksOpenAI handles OAuth automatically
✅ Token refresh handled by client

### 3. Environment Flexibility
✅ Same tests work locally and deployed
✅ Single environment variable to switch
✅ Easy CI/CD integration

### 4. Better Developer Experience
✅ Matches real-world usage patterns
✅ Easier to debug (using real clients)
✅ Clear separation of local vs deployed testing

## Migration Guide

### For Developers

**No code changes needed in tests!**

Tests continue to use `async_client` fixture, which now:
- Uses OpenAI client under the hood
- Handles auth automatically based on environment
- Works the same way in test code

**What you need to do:**

1. **Install updated dependencies:**
   ```bash
   uv sync
   # or
   pip install -e .
   ```

2. **Test locally (same as before):**
   ```bash
   # Start server
   uvicorn server.main:app --port 8000

   # Run tests
   pytest
   ```

3. **Test deployed app (new capability):**
   ```bash
   # Authenticate
   databricks auth login

   # Run tests
   BASE_URL=https://your-workspace.../apps/your-app pytest
   ```

### For CI/CD

**GitHub Actions Example:**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test-local:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -e .
      - name: Start server
        run: uvicorn server.main:app &
      - name: Wait for server
        run: sleep 5
      - name: Run tests
        run: pytest -v

  test-deployed:
    runs-on: ubuntu-latest
    needs: deploy  # Run after deployment
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install -e .
      - name: Configure Databricks
        run: databricks auth login --host ${{ secrets.DATABRICKS_HOST }} --token ${{ secrets.DATABRICKS_TOKEN }}
      - name: Test deployed app
        env:
          BASE_URL: ${{ secrets.APP_URL }}
        run: pytest -v
```

## Testing the Update

### 1. Verify Local Testing Still Works

```bash
cd ~/agent-backend

# Install dependencies
uv sync

# Start server
uvicorn server.main:app --port 8000 &

# Run tests
pytest -v

# Should see: Uses AsyncOpenAI with api_key=""
```

### 2. Verify Deployed Testing Works

```bash
# Deploy app
databricks bundle deploy

# Get app URL
APP_URL=$(databricks apps get agent-backend-dev --format json | jq -r '.url')

# Test deployed app
BASE_URL=$APP_URL pytest tests/test_api_acceptance.py::TestHealthEndpoint -v

# Should see: Uses AsyncDatabricksOpenAI with OAuth
```

## Troubleshooting

### Issue: "AsyncOpenAI not found"

```bash
# Reinstall dependencies
pip install -e .
# or
uv sync
```

### Issue: "401 Unauthorized" when testing deployed app

```bash
# Check authentication
databricks auth profiles

# Re-authenticate
databricks auth login --host https://your-workspace.cloud.databricks.com

# Verify BASE_URL is correct
echo $BASE_URL
```

### Issue: Tests pass locally but fail on deployed app

**Possible causes:**
1. App not fully started - wait a few seconds after deployment
2. Wrong BASE_URL - verify with `databricks apps list`
3. Auth not configured - run `databricks auth login`
4. App permissions - check bundle configuration

## What's Next

With this update, you can now:

1. ✅ Test locally during development (fast, no auth)
2. ✅ Test deployed staging app (realistic, with auth)
3. ✅ Test deployed production app (validation)
4. ✅ Run same tests in CI/CD for both local and deployed
5. ✅ Validate OpenResponses compatibility with real clients

## Questions?

See:
- **`tests/TEST_CLIENT_SETUP.md`** - Detailed client configuration guide
- **`TEST_SUMMARY.md`** - Complete test suite overview
- **`TESTING_QUICKSTART.md`** - Quick start guide

## Summary

The test suite now uses the actual OpenAI/DatabricksOpenAI clients, providing:

- ✅ **Realistic testing** with real client behavior
- ✅ **Automatic authentication** (no manual tokens)
- ✅ **Environment flexibility** (local or deployed)
- ✅ **Better validation** of OpenResponses compatibility

**No changes needed to existing test code** - just set `BASE_URL` to test deployed apps!
