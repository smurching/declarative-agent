# Agent Backend - Test Suite

Comprehensive automated acceptance tests for the Agent Backend API.

## Overview

This test suite validates all aspects of the Agent Backend, from API endpoints to database schema compliance. Tests are organized by functionality and can be run independently or as a complete suite.

## Test Structure

```
tests/
├── conftest.py                    # Pytest fixtures and configuration
├── test_api_acceptance.py         # API acceptance tests
├── test_database.py               # Database layer tests
└── README.md                      # This file
```

## Test Categories

### 1. API Acceptance Tests (`test_api_acceptance.py`)

Tests the public API endpoints from an end-user perspective.

#### TestHealthEndpoint
- ✅ Health check returns 200 OK
- ✅ Response structure validation
- ✅ Status values validation (healthy/unhealthy)

#### TestResponsesEndpointNonStreaming
- ✅ Create response returns 200
- ✅ Response includes ID (resp_abc123 format)
- ✅ Response includes output array
- ✅ Output items have correct structure (role, content)
- ✅ Works with existing conversations
- ✅ Missing user_id returns 422
- ✅ Invalid conversation_id returns 404

#### TestResponsesEndpointStreaming
- ✅ Streaming returns SSE content type
- ✅ SSE events are properly formatted
- ✅ Event types are correct (delta, done)
- ✅ Delta events have correct structure
- ✅ Stream ends with [DONE] marker

#### TestResponsesEndpointBackground
- ✅ Background mode returns immediately
- ✅ Returns in_progress status
- ✅ No output initially (deferred execution)

#### TestGetResponseEndpoint
- ✅ Non-existent response returns 404
- ✅ Can retrieve completed responses
- ✅ Background responses eventually complete

#### TestConversationEndpoints
- ✅ Retrieve conversation with messages
- ✅ Conversation structure validation
- ✅ Messages structure validation
- ✅ Messages ordered by message_index
- ✅ Non-existent conversation returns error
- ✅ Message pagination works (limit, offset)

#### TestMessagePersistence
- ✅ Messages persisted after response creation
- ✅ Multi-turn conversations work correctly

#### TestErrorHandling
- ✅ Invalid JSON returns 422
- ✅ Missing required fields returns 422
- ✅ Invalid role returns 422
- ✅ Empty input array returns error

#### TestDatabaseSchema
- ✅ Conversations have estore-required fields
- ✅ Message index uniqueness enforced
- ✅ Message content serialization works

### 2. Database Layer Tests (`test_database.py`)

Tests database models, queries, and data integrity.

#### TestConversationModel
- ✅ Create conversation
- ✅ Retrieve conversation by ID
- ✅ Non-existent conversation returns None

#### TestMessageModel
- ✅ Save message
- ✅ JSON content serialization
- ✅ Message ordering by index
- ✅ Pagination (limit, offset)
- ✅ Get next message index
- ✅ Next index for empty conversation

#### TestResponseModel
- ✅ Create response record
- ✅ Retrieve response record
- ✅ Update response progress
- ✅ Update status to completed
- ✅ Update status to failed

#### TestCascadeDeletes
- ✅ Delete conversation deletes messages
- ✅ Delete conversation deletes responses

#### TestDataIntegrity
- ✅ Message requires valid conversation
- ✅ Message index unique per conversation
- ✅ Conversation requires user and workspace

## Running Tests

### Run All Tests

```bash
cd ~/agent-backend
pytest
```

### Run Specific Test File

```bash
pytest tests/test_api_acceptance.py
pytest tests/test_database.py
```

### Run Specific Test Class

```bash
pytest tests/test_api_acceptance.py::TestHealthEndpoint
pytest tests/test_database.py::TestConversationModel
```

### Run Specific Test

```bash
pytest tests/test_api_acceptance.py::TestHealthEndpoint::test_health_check_returns_200
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=server --cov-report=html
```

## Test Fixtures

### Provided Fixtures (in `conftest.py`)

| Fixture | Description |
|---------|-------------|
| `async_client` | AsyncClient for making API requests |
| `db_session` | Database session for direct DB access |
| `sample_user_id` | Test user ID (12345) |
| `sample_workspace_id` | Test workspace ID |
| `sample_conversation_payload` | Non-streaming request payload |
| `sample_streaming_payload` | Streaming request payload |
| `sample_background_payload` | Background mode payload |
| `existing_conversation` | Pre-created conversation with 3 messages |

## Test Coverage Summary

| Component | Coverage |
|-----------|----------|
| **API Endpoints** | ✅ Complete |
| `/health` | ✅ 3 tests |
| `POST /responses` (non-streaming) | ✅ 8 tests |
| `POST /responses` (streaming) | ✅ 5 tests |
| `POST /responses` (background) | ✅ 2 tests |
| `GET /responses/{id}` | ✅ 3 tests |
| `GET /conversations/{id}` | ✅ 5 tests |
| `GET /conversations/{id}/messages` | ✅ 1 test |
| **Database Models** | ✅ Complete |
| Conversation CRUD | ✅ 3 tests |
| Message CRUD | ✅ 6 tests |
| Response CRUD | ✅ 5 tests |
| Cascade deletes | ✅ 2 tests |
| Data integrity | ✅ 3 tests |
| **Error Handling** | ✅ 4 tests |
| **Schema Compliance** | ✅ 3 tests |

**Total Tests:** ~70 tests

## Prerequisites for Running Tests

### 1. Environment Configuration

Create `.env` file with test database configuration:

```bash
# Copy example
cp .env.example .env

# Edit with your Databricks details
PGHOST=your-lakebase-host
PGUSER=your-username
PGDATABASE=databricks_postgres
WORKSPACE_ID=12345
```

### 2. Database Setup

Tests use a separate test database schema to avoid affecting production data. Ensure you have:

- Lakebase instance running
- Databricks authentication configured
- Database permissions (CAN_CONNECT_AND_CREATE)

### 3. LLM Endpoint

Some tests make actual LLM calls. Ensure you have:

- Databricks serving endpoint available
- Endpoint configured in environment (default: `databricks-gpt-5-2`)

## Test Environment Variables

Tests respect the following environment variables:

- `PGHOST` - Database host
- `PGPORT` - Database port (default: 5432)
- `PGUSER` - Database user
- `PGDATABASE` - Database name
- `WORKSPACE_ID` - Databricks workspace ID
- `DATABRICKS_SERVING_ENDPOINT` - LLM endpoint name

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=server --cov-report=xml
```

## Known Limitations

1. **Test Database Isolation**: Currently uses same database with different schema. In production, use a completely separate test database.

2. **LLM Calls**: Some tests make real LLM calls, which:
   - Require active serving endpoint
   - May incur costs
   - Can be slow

3. **Async Test Setup**: Test database setup is complex due to async requirements. Consider using test containers for better isolation.

## Future Enhancements

- [ ] Add integration tests with mock LLM
- [ ] Add load/performance tests
- [ ] Add test containers for database isolation
- [ ] Add mutation testing
- [ ] Add E2E tests with real frontend
- [ ] Add API contract tests (OpenAPI spec validation)

## Troubleshooting

### Tests Fail with "Connection Refused"

- Ensure Lakebase instance is running
- Check database credentials in `.env`
- Verify Databricks authentication

### Tests Fail with "LLM Endpoint Not Found"

- Check serving endpoint name in `.env`
- Ensure endpoint is deployed and running
- Verify permissions (CAN_QUERY)

### Tests Timeout

- Increase pytest timeout: `pytest --timeout=60`
- Check network connectivity to Databricks
- Verify no rate limiting

### Database Tests Fail

- Ensure migrations have been run
- Check database permissions
- Verify schema matches models

## Contributing

When adding new functionality:

1. Write tests first (TDD)
2. Ensure all existing tests pass
3. Add test documentation to this README
4. Update coverage summary

## Test Standards

- All tests should be async-aware
- Use fixtures for common setup
- Tests should be independent (no shared state)
- Use descriptive test names
- Add docstrings explaining what's being tested
- Clean up resources in teardown

## Questions?

See main [README.md](../README.md) for project documentation.
