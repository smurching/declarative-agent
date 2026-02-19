# Deploy Your Agent to Databricks Apps

This template provides the simplest way to deploy a declarative agent to Databricks Apps using the CLI.

## Structure

```
app_template/
├── my_agent.yaml      # Your agent definition (customize this!)
├── requirements.txt   # Installs CLI from GitHub
├── app.yaml          # Databricks App runtime configuration
└── README.md         # This file
```

## Quick Start

### 1. Customize Your Agent

Edit `my_agent.yaml` to define your agent:

```yaml
name: "support-agent"
description: "Customer support assistant"
model: "databricks-gpt-5-2"
temperature: 0.7
instructions: |
  You are a helpful customer support agent.
  Be professional, empathetic, and concise.
supports_streaming: true
supports_background: false
```

### 2. Deploy to Databricks

First, ensure the backend is deployed (only needs to be done once):

```bash
cd ~/declarative-agent
databricks bundle deploy --target dev
```

Then deploy your agent:

```bash
cd app_template

# Update databricks.yml to add your agent app
# See example in parent directory's databricks.yml

databricks bundle deploy --target dev
```

### 3. Test Your Agent

```bash
# Get access token
TOKEN=$(databricks auth token --output json | jq -r '.access_token')

# Test the agent
curl -X POST https://dev-my-agent.databricksapps.com/invocations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## How It Works

The `app.yaml` file runs:

```bash
declarative-agent serve my_agent.yaml --backend-url $BACKEND_URL
```

This single command:
1. Loads your agent from `my_agent.yaml`
2. Connects to the backend API
3. Serves the agent at the `/invocations` endpoint

**No Python code needed!** Just YAML configuration.

## Configuration Options

### Agent YAML Fields

- `name`: Agent identifier (required)
- `description`: Human-readable description
- `model`: LLM model to use (default: "databricks-gpt-5-2")
- `temperature`: Sampling temperature (0.0-1.0)
- `instructions`: System prompt for the agent
- `supports_streaming`: Enable streaming responses (default: true)
- `supports_background`: Enable background execution (default: false)

### Environment Variables (app.yaml)

The app.yaml can reference variables:

```yaml
env:
  - name: BACKEND_URL
    value: "https://${var.backend_app_name}.databricksapps.com"
  - name: WORKSPACE_ID
    value: "${var.workspace_id}"
```

Define these in your `databricks.yml`:

```yaml
variables:
  backend_app_name:
    default: "dev-backend"
  workspace_id:
    default: "your-workspace-id"
```

## Deployment Architecture

```
User Request
    ↓
Agent App (this template)
    ├── Loads: my_agent.yaml
    ├── Runs: declarative-agent serve
    └── Endpoint: /invocations
    ↓
Backend App (shared)
    ├── Handles: Agent execution, tools, memory
    ├── Database: Lakebase for conversations
    └── LLM: Databricks Model Serving
```

## Comparison: Before vs After

**Before** (Custom Python code):
```
agent_app/
├── main.py              # 200+ lines of FastAPI code
├── requirements.txt
└── examples/
    └── agents/
        └── my_agent.yaml
```

**After** (CLI-based):
```
app_template/
├── my_agent.yaml        # Just your config!
├── requirements.txt     # Install CLI
└── app.yaml            # Runtime config
```

**Result**: Deploy agents with zero Python code!

## Local Testing

Before deploying, test locally:

```bash
# Install CLI
cd ~/declarative-agent
pip install -e .

# Serve locally
cd app_template
declarative-agent serve my_agent.yaml

# Test in another terminal
curl -X POST http://localhost:8001/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": "Hello"}], "stream": false}'
```

## Troubleshooting

### Backend Not Found

**Error**: `Error: Backend not running at https://...`

**Solution**: Ensure backend app is deployed first:
```bash
cd ~/declarative-agent
databricks bundle deploy --target dev
```

### Agent YAML Not Found

**Error**: `Agent file not found`

**Solution**: Ensure `my_agent.yaml` exists in the same directory as `app.yaml`

### Permission Errors

**Error**: `Permission denied` or `403 Forbidden`

**Solution**: Ensure your agent app has `CAN_USE` permission for the backend app in `app.yaml`

## Advanced Usage

### Multiple Agents

Deploy multiple agents by creating separate directories:

```
agents/
├── support-agent/
│   ├── my_agent.yaml
│   ├── app.yaml
│   └── requirements.txt
├── sales-agent/
│   ├── my_agent.yaml
│   ├── app.yaml
│   └── requirements.txt
```

### Custom Models

Use different LLM models:

```yaml
# my_agent.yaml
model: "databricks-llama-3-70b"  # Or any Model Serving endpoint
temperature: 0.5
```

### Add Tools (Future)

Coming soon: Tool definitions in YAML for UC functions, vector search, etc.

## Resources

- [Declarative Agent Docs](https://github.com/smurching/declarative-agent)
- [Databricks Apps Documentation](https://docs.databricks.com/en/apps/index.html)
- [Getting Started Guide](../docs/GETTING_STARTED.md)
