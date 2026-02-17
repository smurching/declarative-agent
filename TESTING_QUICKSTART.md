# Testing Quick Start Guide

Quick guide to get the test suite running.

## Prerequisites Check

```bash
# 1. Check Python version (need 3.12+)
python --version

# 2. Check if in project directory
cd ~/agent-backend

# 3. Check if dependencies installed
pip list | grep pytest
```

## Setup Steps

### 1. Install Dependencies

```bash
# Using pip
pip install -e .

# OR using uv (recommended)
uv sync
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your Databricks configuration
nano .env  # or use your preferred editor
```

**Required environment variables:**
```bash
PGHOST=your-lakebase-host.cloud.databricks.com
PGPORT=5432
PGUSER=your-username
PGDATABASE=databricks_postgres
WORKSPACE_ID=12345
DATABRICKS_SERVING_ENDPOINT=databricks-gpt-5-2
```

### 3. Verify Databricks Authentication

```bash
# Check if databricks CLI is authenticated
databricks auth profiles

# If not authenticated, run:
databricks auth login --host https://your-workspace.cloud.databricks.com
```

### 4. Verify Database Access

```bash
# Test database connection (optional)
python -c "
from server.config import get_settings
from server.auth.databricks import get_databricks_oauth_token
import asyncio

async def test_db():
    settings = get_settings()
    print(f'Database host: {settings.pghost}')
    token = await get_databricks_oauth_token()
    print('✓ OAuth token obtained')

asyncio.run(test_db())
"
```

## Running Tests

### Test Locally (Default - No Auth)

```bash
# 1. Start local server (in another terminal)
uvicorn server.main:app --port 8000

# 2. Run tests
pytest
```

**Uses:** `openai.AsyncOpenAI` with empty API key (no auth)

**Expected output:**
```
======================== test session starts =========================
collected 90 items

tests/test_api_acceptance.py ...................... [ 25%]
tests/test_database.py .................. [ 45%]
tests/test_integration.py ............. [100%]

======================== 90 passed in 45.23s =========================
```

### Test Deployed App (With Databricks Auth)

```bash
# Test against deployed Databricks App
BASE_URL=https://your-workspace.cloud.databricks.com/apps/your-app pytest
```

**Uses:** `databricks_openai.AsyncDatabricksOpenAI` with automatic OAuth

**Requirements:**
- Databricks CLI authenticated: `databricks auth login`
- App deployed and running

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
# API tests only
pytest tests/test_api_acceptance.py -v

# Database tests only
pytest tests/test_database.py -v

# Integration tests only
pytest tests/test_integration.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_api_acceptance.py::TestHealthEndpoint -v
```

### Run Specific Test

```bash
pytest tests/test_api_acceptance.py::TestHealthEndpoint::test_health_check_returns_200 -v
```

### Run Tests with Output

```bash
# Show print statements
pytest -s

# Show detailed output
pytest -vv
```

## Common Issues and Fixes

### Issue: "Connection refused" error

**Cause:** Database not accessible

**Fix:**
```bash
# 1. Check Lakebase instance is running
databricks sql warehouses list

# 2. Verify credentials in .env
cat .env | grep PG

# 3. Test authentication
databricks auth token
```

### Issue: "ModuleNotFoundError"

**Cause:** Dependencies not installed

**Fix:**
```bash
# Reinstall dependencies
pip install -e .

# OR
uv sync
```

### Issue: "LLM endpoint not found"

**Cause:** Serving endpoint not available or misconfigured

**Fix:**
```bash
# 1. Check endpoint exists
databricks serving-endpoints list

# 2. Verify endpoint name in .env
cat .env | grep DATABRICKS_SERVING_ENDPOINT

# 3. Update .env with correct endpoint name
```

### Issue: Tests timeout

**Cause:** LLM calls taking too long

**Fix:**
```bash
# Increase timeout
pytest --timeout=120

# Or skip slow tests
pytest -m "not slow"
```

### Issue: "Permission denied" on database

**Cause:** Insufficient database permissions

**Fix:**
- Verify you have CAN_CONNECT_AND_CREATE permission on Lakebase instance
- Check Databricks bundle configuration grants correct permissions

## Test Configuration

### Skip Integration Tests

Integration tests make real API calls and can be slow:

```bash
# Skip integration tests
pytest -m "not integration"
```

### Run Only Unit Tests

```bash
# Run only database tests (fast)
pytest tests/test_database.py
```

### Custom Test Database

To use a different test database:

```bash
# Set environment variable
export PGDATABASE=test_databricks_postgres

# Run tests
pytest
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -e .
      - name: Run tests
        env:
          PGHOST: ${{ secrets.PGHOST }}
          PGUSER: ${{ secrets.PGUSER }}
          PGDATABASE: ${{ secrets.PGDATABASE }}
          WORKSPACE_ID: ${{ secrets.WORKSPACE_ID }}
        run: pytest -v
```

## Debugging Tests

### Run Single Test with Debug

```bash
# Run with debug output
pytest tests/test_api_acceptance.py::TestHealthEndpoint::test_health_check_returns_200 -vv -s
```

### Use pdb for Interactive Debugging

Add breakpoint in test:
```python
def test_something():
    import pdb; pdb.set_trace()
    # Test code here
```

Run with pdb:
```bash
pytest --pdb
```

### View Test Logs

```bash
# Show logs during test run
pytest --log-cli-level=DEBUG
```

## Performance Tips

### Run Tests in Parallel

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4
```

### Cache Test Results

```bash
# Only run failed tests from last run
pytest --lf

# Run failed first, then others
pytest --ff
```

## Test Coverage

### Generate Coverage Report

```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage
pytest --cov=server --cov-report=html

# View report
open htmlcov/index.html
```

## Next Steps

1. ✅ Run basic test suite: `pytest`
2. ✅ Review failing tests (if any)
3. ✅ Check coverage: `pytest --cov=server`
4. ✅ Review test files in `tests/` directory
5. ✅ Add custom tests for your specific use cases

## Getting Help

- **Test Documentation:** See `tests/README.md`
- **Test Summary:** See `TEST_SUMMARY.md`
- **Project README:** See `README.md`

## Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -v` | Verbose output |
| `pytest -s` | Show print statements |
| `pytest -x` | Stop on first failure |
| `pytest -k "test_health"` | Run tests matching pattern |
| `pytest --lf` | Run last failed tests |
| `pytest --collect-only` | List all tests without running |
| `pytest --markers` | List available markers |

## Success Indicators

You'll know tests are working when you see:

```
======================== 90 passed in 45.23s =========================
```

If you see failures:
1. Read the error message carefully
2. Check the "Common Issues" section above
3. Review the specific test file for context
4. Check environment configuration

Happy testing! 🧪
