# Declarative Agent CLI - Quick Reference

## Installation

```bash
pip install -e .
```

## Basic Commands

### Serve an Agent
```bash
# Auto-starts backend if needed
declarative-agent serve my_agent.yaml

# Custom port
declarative-agent serve my_agent.yaml --port 8002

# Use existing backend
declarative-agent serve my_agent.yaml --backend-url http://backend:8000

# Development mode with auto-reload
declarative-agent serve my_agent.yaml --reload
```

### Start Backend Only
```bash
declarative-agent backend
declarative-agent backend --port 8000 --reload
```

### Get Help
```bash
declarative-agent --help
declarative-agent serve --help
declarative-agent backend --help
```

## Agent YAML Format

```yaml
name: "my-agent"
description: "Agent description"
model: "databricks-gpt-5-2"
temperature: 0.7
instructions: |
  System instructions for your agent.
  Can be multi-line.
supports_streaming: true
supports_background: false
```

## Testing Your Agent

### Health Check
```bash
curl http://localhost:8001/health
```

### Non-Streaming Request
```bash
curl -X POST http://localhost:8001/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### Streaming Request
```bash
curl -X POST http://localhost:8001/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## Common Workflows

### Quick Test Locally
```bash
# Create agent
cat > test_agent.yaml << 'EOF'
name: test
model: databricks-gpt-5-2
instructions: You are a helpful assistant.
EOF

# Serve it
declarative-agent serve test_agent.yaml

# Test it (in another terminal)
curl -X POST http://localhost:8001/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": "Hi"}], "stream": false}'
```

### Deploy to Databricks

1. **Create agent YAML** in `app_template/my_agent.yaml`
2. **Deploy**: `databricks bundle deploy --target dev`
3. **Test**: See app_template/README.md for curl commands

## Troubleshooting

### Port Already in Use
```bash
# Use different port
declarative-agent serve agent.yaml --port 8002
```

### Backend Not Found
```bash
# Ensure backend URL is correct
declarative-agent serve agent.yaml --backend-url http://localhost:8000

# Or let it auto-start
declarative-agent serve agent.yaml  # Will auto-start if localhost
```

### Check Running Processes
```bash
# List processes
ps aux | grep -E "declarative-agent|uvicorn"

# Kill processes
pkill -f "declarative-agent"
pkill -f "uvicorn"
```

## Environment Variables

The CLI sets these automatically:
- `AGENT_YAML_PATH` - Path to agent YAML file
- `BACKEND_APP_URL` - Backend API URL
- `DB_TYPE` - Database type (sqlite for local)

## Command Options

### serve
- `--port` - Agent app port (default: 8001)
- `--host` - Host to bind (default: 0.0.0.0)
- `--backend-url` - Backend URL (default: http://localhost:8000)
- `--backend-port` - Backend port if auto-starting (default: 8000)
- `--no-backend` - Don't auto-start backend
- `--reload` - Enable auto-reload

### backend
- `--port` - Backend port (default: 8000)
- `--host` - Host to bind (default: 0.0.0.0)
- `--reload` - Enable auto-reload

## Example Agents

Located in `agent_app/examples/agents/`:
- `assistant.yaml` - Simple helpful assistant
- `data_analyst.yaml` - Data analysis agent
- `code_reviewer.yaml` - Code review agent
- `sales_assistant.yaml` - Sales support agent
- `hr_support.yaml` - HR support agent

Try them:
```bash
declarative-agent serve agent_app/examples/agents/assistant.yaml
```

## Advanced Usage

### Use Pre-Started Backend
```bash
# Terminal 1: Start backend
declarative-agent backend --port 8000

# Terminal 2: Serve agent (reuses backend)
declarative-agent serve my_agent.yaml --backend-url http://localhost:8000
```

### Development with Auto-Reload
```bash
declarative-agent serve my_agent.yaml --reload
# Edit my_agent.yaml and changes auto-apply
```

### Remote Backend
```bash
declarative-agent serve my_agent.yaml \
  --backend-url https://my-backend.databricksapps.com \
  --no-backend  # Don't try to auto-start remote
```

## API Endpoints

When serving an agent, these endpoints are available:

- `GET /` - Agent info
- `GET /health` - Health check
- `POST /invocations` - Chat with agent
- `GET /task/{task_id}` - Get background task result
- `GET /conversations/{conversation_id}` - Get conversation history

## Response Format

```json
{
  "id": "resp_abc123",
  "status": null,
  "output": [
    {
      "role": "assistant",
      "content": "Agent response here"
    }
  ],
  "conversation_id": "conv_xyz789"
}
```

## Tips

1. **Always use absolute or relative paths for YAML files**
2. **Backend auto-starts only for localhost URLs**
3. **Press Ctrl+C to gracefully stop both agent and backend**
4. **Use `--reload` during development for faster iteration**
5. **Check logs in the terminal for debugging**

## Getting Help

- GitHub: https://github.com/smurching/declarative-agent
- Docs: See `docs/GETTING_STARTED.md`
- Issues: https://github.com/smurching/declarative-agent/issues
