# Test Migration Guide - Using OpenAI Client Directly

## Overview

Tests should use the `openai_client` fixture directly instead of extracting the underlying httpx client. The OpenAI SDK provides `post()`, `get()`, etc. methods that work with custom endpoints while maintaining proper authentication.

## Pattern to Follow

### ❌ Old Pattern (using async_client)

```python
@pytest.mark.asyncio
async def test_create_response(
    self, async_client: AsyncClient, sample_conversation_payload
):
    """Test creating a response."""
    response = await async_client.post("/responses", json=sample_conversation_payload)
    assert response.status_code == 200
```

### ✅ New Pattern (using openai_client)

```python
@pytest.mark.asyncio
async def test_create_response(
    self, openai_client, sample_conversation_payload
):
    """Test creating a response."""
    # OpenAI client's post() method works with custom endpoints
    response = await openai_client.post("/responses", json=sample_conversation_payload)
    assert response.status_code == 200
```

## Migration Steps

### 1. Replace Fixture Parameter

**Before:**
```python
async def test_something(self, async_client: AsyncClient, ...):
```

**After:**
```python
async def test_something(self, openai_client, ...):
```

### 2. Use Client Methods Directly

**For POST requests:**
```python
# Before
response = await async_client.post("/responses", json=payload)

# After
response = await openai_client.post("/responses", json=payload)
```

**For GET requests:**
```python
# Before
response = await async_client.get("/health")

# After
response = await openai_client.get("/health")
```

**For streaming:**
```python
# Before
response = await async_client.post("/responses", json=payload)
async for line in response.aiter_lines():
    ...

# After
response = await openai_client.post("/responses", json=payload)
async for line in response.aiter_lines():
    ...
```

## When to Keep async_client

Keep using `async_client` only when you need raw httpx features not available in the OpenAI client's API. For most tests, `openai_client` should be sufficient.

**Example where async_client might be needed:**
```python
# If OpenAI client doesn't support certain httpx features
async def test_with_custom_headers(self, async_client):
    # Use async_client if you need low-level httpx control
    response = await async_client.get(
        "/endpoint",
        headers={"Custom-Header": "value"}
    )
```

## Files to Update

### Priority 1: API Tests
- `test_api_acceptance.py` - Replace all `async_client` with `openai_client`
  - TestHealthEndpoint
  - TestResponsesEndpointNonStreaming
  - TestResponsesEndpointStreaming
  - TestResponsesEndpointBackground
  - TestGetResponseEndpoint
  - TestConversationEndpoints

### Priority 2: Integration Tests
- `test_integration.py` - Replace all `async_client` with `openai_client`
  - TestCompleteConversationFlow
  - TestBackgroundModeFlow
  - TestErrorRecoveryFlows
  - TestConcurrentRequests

### Priority 3: Database Tests
- `test_database.py` - Keep as is (uses db_session, not HTTP client)

## Benefits of This Approach

1. **Uses Real Client**: Tests use the actual OpenAI/Databricks client methods
2. **Proper Auth**: Authentication handled automatically by client
3. **Cleaner Code**: Direct client usage, no extraction of internal httpx client
4. **Type Safety**: Better IDE support with client methods
5. **Future Proof**: Works if OpenAI SDK adds official `responses` endpoint support

## Example: Complete Test Class Update

### Before
```python
class TestResponsesEndpointNonStreaming:
    """Tests for POST /responses in non-streaming mode."""

    @pytest.mark.asyncio
    async def test_create_response_success(
        self, async_client: AsyncClient, sample_conversation_payload
    ):
        """Test creating a response."""
        response = await async_client.post("/responses", json=sample_conversation_payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_response(self, async_client: AsyncClient):
        """Test getting a response."""
        response = await async_client.get("/responses/resp_123")
        assert response.status_code == 200
```

### After
```python
class TestResponsesEndpointNonStreaming:
    """Tests for POST /responses in non-streaming mode."""

    @pytest.mark.asyncio
    async def test_create_response_success(
        self, openai_client, sample_conversation_payload
    ):
        """Test creating a response."""
        response = await openai_client.post("/responses", json=sample_conversation_payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_response(self, openai_client):
        """Test getting a response."""
        response = await openai_client.get("/responses/resp_123")
        assert response.status_code == 200
```

## Automated Migration Script

You can use this find-replace pattern:

```bash
# In test files, replace:
find tests/ -name "test_*.py" -type f -exec sed -i '' \
  -e 's/async_client: AsyncClient/openai_client/g' \
  -e 's/async_client\./openai_client./g' \
  {}  \;
```

Or manually update each test file following the pattern above.

## Testing the Migration

After updating:

```bash
# Run tests to ensure they still pass
pytest tests/test_api_acceptance.py -v

# Should see tests using OpenAI client
pytest tests/test_api_acceptance.py::TestResponsesEndpointNonStreaming -v
```

## Summary

**Simple rule:** Replace `async_client: AsyncClient` with `openai_client` and change `async_client.post()` to `openai_client.post()`. The OpenAI SDK handles the rest!
