# Declarative Agent Framework - Technical Specification

**Version:** 1.0
**Date:** February 14, 2026
**Authors:** Sid Murching

## Executive Summary

This document specifies a production-ready declarative agent framework that enables developers to build, deploy, and iterate on AI agents with minimal code. The framework decouples agent authoring (YAML/SDK), runtime execution (hosted agent loop), and frontend UX (customizable chat/UI), while providing best-in-class observability, governance, and conversation management.

**Key Design Principles:**
1. **Portability**: Support multiple agent SDKs (OpenAI Agents, LangChain, Claude SDK, custom) through standardized interfaces
2. **Declarative-First**: YAML configuration for 80% use cases, SDK escape hatches for advanced needs
3. **Production-Ready**: Built-in tracing, conversation storage, feedback collection, and governance
4. **Open Standards**: Based on OpenResponses spec with backwards-compatible extensions
5. **Databricks-Native**: Deep integration with UC (tables, functions, volumes), Genie, and platform auth

**Existing Components to Leverage:**
- **aroll** - Declarative framework with YAML configs, async execution, multi-provider support
- **MAS (Supervisor Agent)** - Aroll-based orchestration layer with streaming and multi-tool coordination
- **OpenResponses** - Standard API spec for agent invocation and streaming
- **e2e-chatbot-app-next** - Production-ready chat UI with Vercel AI SDK integration

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Declarative Agent Specification](#2-declarative-agent-specification)
3. [Runtime: Agent Loop & Execution](#3-runtime-agent-loop--execution)
4. [Agent Invocation API (OpenResponses++)](#4-agent-invocation-api-openresponses)
5. [Conversation Management & Memory](#5-conversation-management--memory)
6. [Frontend & UI Framework](#6-frontend--ui-framework)
7. [Governance & Permissions](#7-governance--permissions)
8. [Observability & Feedback](#8-observability--feedback)
9. [Implementation Phases](#9-implementation-phases)
10. [Examples & Use Cases](#10-examples--use-cases)

---

## 1. Architecture Overview

### 1.1 Three-Layer Architecture

The framework separates concerns into three decoupled layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHORING LAYER                           │
│  (How you define your agent)                                 │
│                                                               │
│  • Declarative YAML config (aroll-based)                     │
│  • SDK for advanced use cases (TypeScript/Python)            │
│  • Visual agent builder (future)                             │
│  • Import from other SDKs (LangChain, OpenAI, CrewAI)        │
└─────────────────────────────────────────────────────────────┘
                            ↓ Upload/Deploy
┌─────────────────────────────────────────────────────────────┐
│                     RUNTIME LAYER                            │
│  (Where your agent executes)                                 │
│                                                               │
│  • Hosted agent loop (based on MAS/aroll)                    │
│  • Conversation storage (One Chat / estore)                  │
│  • Session management & state                                │
│  • Tool execution environment                                │
│  • Tracing & logging (MLflow)                                │
│  • Background/long-running execution                         │
└─────────────────────────────────────────────────────────────┘
                            ↑ Invoke                ↓ Stream
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                            │
│  (How users interact with your agent)                        │
│                                                               │
│  • Chat UI (e2e-chatbot-app-next template)                   │
│  • Custom UIs (Vercel AI SDK + OpenResponses)                │
│  • Document editors with inline agents                       │
│  • Voice/multimodal interfaces (future)                      │
│  • Embedded in other apps (Sheets, Meet, etc.)               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Key Interfaces

| Interface | Purpose | Standard |
|-----------|---------|----------|
| **Authoring → Runtime** | Upload agent config, register tools | Agent Spec Format (YAML/JSON) |
| **Frontend ↔ Runtime** | Invoke agent, stream responses | OpenResponses++ API |
| **Runtime → Memory** | Store/retrieve conversations | Conversations API (OpenAI-compatible) |
| **Runtime → Tools** | Execute tools on behalf of user | MCP Protocol + UC APIs |
| **Runtime → Observability** | Log traces, collect feedback | MLflow Traces + UC Tables |

### 1.3 Deployment Model

```
Developer                    Databricks Platform
   │                                │
   │  1. Define agent.yaml          │
   │     (tools, prompt, model)     │
   │                                │
   │  2. databricks bundle deploy   │
   ├───────────────────────────────→│
   │                                │  Creates:
   │                                │  • Service Principal
   │                                │  • Agent Runtime (serverless)
   │                                │  • Conversation Storage (estore)
   │                                │  • Trace Logging (MLflow)
   │                                │
   │  3. User invokes via UI        │
   │     POST /mlflow/v1/responses  │
   ├───────────────────────────────→│
   │                                │  Executes:
   │                                │  • Loads agent config
   │                                │  • Runs agentic loop
   │  4. Streams response           │  • Calls tools on-behalf-of user
   │     (OpenResponses events)     │  • Logs traces
   │←───────────────────────────────┤  • Updates conversation
   │                                │
```

---

## 2. Declarative Agent Specification

### 2.1 Agent YAML Format

Building on aroll's existing YAML structure, we define a standard agent specification:

```yaml
# agent.yaml - Declarative agent configuration
name: sales_assistant
version: 1.0
description: "Helps sales reps find customer data and create follow-up tasks"

# Model configuration
model:
  provider: databricks  # databricks | openai | anthropic | custom
  name: databricks-claude-sonnet-4-5
  temperature: 0.7
  max_output_tokens: 4096

# System prompt
prompt:
  system: |
    You are a sales assistant helping reps at Acme Corp.
    Always be professional and concise.
    When querying data, explain your findings clearly.
  user:
    mode: append  # prepend | append | replace
    prompt: "Remember to cite your sources when referencing data."

# Tools available to the agent
tools:
  # UC Table tool
  - type: table
    name: customer_data
    description: "Query customer information and purchase history"
    table_name: main.sales.customers
    permission: on_behalf_of_user  # on_behalf_of_user | as_service_principal
    approval_policy: always_allow  # always_allow | always_ask | smart

  # Genie Space tool
  - type: genie
    name: revenue_analyst
    description: "Analyze revenue trends and forecasts"
    space_id: "01f0695490611f89bba0a496dbdd840c"
    permission: on_behalf_of_user
    approval_policy: always_allow

  # UC Function tool
  - type: uc_function
    name: create_task
    description: "Create a follow-up task in the CRM"
    function_name: main.sales.create_crm_task
    permission: on_behalf_of_user
    approval_policy: always_ask  # User must confirm before creating tasks

  # MCP Server tool
  - type: mcp
    name: salesforce_api
    description: "Query and update Salesforce records"
    connection_name: salesforce_prod  # UC connection
    permission: on_behalf_of_user
    approval_policy: always_ask

  # Web Search (built-in)
  - type: web_search
    name: company_research
    description: "Search the web for company information"
    approval_policy: always_allow

  # Code Interpreter (built-in)
  - type: code_interpreter
    name: data_analysis
    description: "Analyze data with Python"
    approval_policy: always_allow

# Agent behavior configuration
behavior:
  recursion_limit: 10  # Max tool call depth
  parallel_tools: true  # Allow parallel tool execution
  streaming: true  # Stream responses
  interrupt_on_tool_approval: true  # Pause for tool approvals

# Conversation settings
conversation:
  auto_compact: true  # Auto-compact when approaching context limit
  compact_strategy: summarize  # summarize | truncate
  memory:
    # Short-term: conversation history (automatic)
    short_term: true
    # Long-term: facts to remember across conversations
    long_term:
      enabled: false  # Future: enable long-term memory
      storage: main.sales.agent_memory

# Observability
tracing:
  enabled: true
  destination:
    type: table
    name: main.sales.agent_traces
  include_tool_inputs: true
  include_tool_outputs: true
  redact_pii: true  # Redact PII from traces

feedback:
  enabled: true
  destination:
    type: table
    name: main.sales.agent_feedback

# Governance
governance:
  max_cost_per_session: 0.50  # Max $ per conversation
  max_duration_seconds: 300  # Max execution time
  allowed_principals:  # Who can invoke this agent
    - users  # All workspace users
    - groups: ["sales_team"]
  rate_limit:
    requests_per_minute: 60
    requests_per_hour: 500
```

### 2.2 Mapping to Existing aroll Config

The agent spec maps to aroll's configuration structure:

| Agent Spec Field | aroll Config Field | Notes |
|-----------------|-------------------|-------|
| `model.*` | `env.llm_endpoint_name`, `env.temperature` | Direct mapping |
| `prompt.system` | `env.prompt.system.prompt` | aroll supports templating |
| `tools[]` | `env.tools[]` | Extended with UC-specific tools |
| `behavior.recursion_limit` | `env.recursion_limit` | Same concept |
| `behavior.parallel_tools` | Automatic in aroll | Enabled by provider support |
| `tracing.destination` | `output.mlflow.*` | Extended to support UC tables |

### 2.3 Tool Configuration Schema

Each tool has a common structure:

```typescript
interface ToolConfig {
  type: 'table' | 'genie' | 'uc_function' | 'mcp' | 'web_search' | 'code_interpreter' | 'custom';
  name: string;  // Unique identifier for this tool
  description: string;  // What this tool does (used by LLM for selection)

  // Auth/execution context
  permission: 'on_behalf_of_user' | 'as_service_principal';
  approval_policy: 'always_allow' | 'always_ask' | 'smart';  // 'smart' = ask for state-changing ops

  // Type-specific fields
  [key: string]: any;
}
```

**Tool-specific fields:**

```typescript
// UC Table Tool
interface TableTool extends ToolConfig {
  type: 'table';
  table_name: string;  // Fully qualified: catalog.schema.table
  query_examples?: string[];  // Optional: few-shot examples
}

// Genie Space Tool
interface GenieTool extends ToolConfig {
  type: 'genie';
  space_id: string;
}

// UC Function Tool
interface UCFunctionTool extends ToolConfig {
  type: 'uc_function';
  function_name: string;  // Fully qualified: catalog.schema.function
}

// MCP Server Tool
interface MCPTool extends ToolConfig {
  type: 'mcp';
  connection_name: string;  // UC connection name
  server_url?: string;  // Override from connection
}
```

### 2.4 SDK for Advanced Use Cases

For cases where YAML is insufficient, provide TypeScript/Python SDKs:

```typescript
// TypeScript SDK example
import { Agent, TableTool, GenieTool } from '@databricks/agent-framework';

const agent = new Agent({
  name: 'advanced_assistant',
  model: {
    provider: 'databricks',
    name: 'databricks-claude-sonnet-4-5',
  },

  // Programmatic prompt construction
  prompt: (context) => ({
    system: `You are assisting ${context.user.name} with ${context.task}`,
    user: 'Be concise and cite sources.',
  }),

  // Programmatic tool configuration
  tools: [
    new TableTool({
      name: 'customer_data',
      tableName: 'main.sales.customers',
      // Custom authorization logic
      authorize: async (user, query) => {
        return user.hasPermission('sales.read');
      },
    }),

    // Custom tool implementation
    {
      name: 'custom_api',
      description: 'Call internal API',
      execute: async (args, context) => {
        const response = await fetch(`/api/${args.endpoint}`);
        return response.json();
      },
    },
  ],

  // Custom conversation handler
  onMessage: async (message, context) => {
    // Pre-processing logic
    console.log(`User ${context.user.id} sent: ${message}`);
  },
});

// Deploy to Databricks
await agent.deploy({
  workspace: 'https://my-workspace.cloud.databricks.com',
  resourceGroup: 'sales-agents',
});
```

### 2.5 Importing from Other Agent SDKs

Support importing agents from popular frameworks:

```typescript
// Import LangChain agent
import { fromLangChain } from '@databricks/agent-framework/adapters';
import { createReactAgent } from 'langchain/agents';

const langchainAgent = createReactAgent({ ... });
const databricksAgent = fromLangChain(langchainAgent, {
  tracing: { destination: 'main.default.traces' },
  conversation: { storage: 'estore' },
});

await databricksAgent.deploy();
```

```python
# Import OpenAI Swarm agent
from databricks.agent_framework.adapters import from_openai_swarm
from swarm import Swarm, Agent

swarm_agent = Agent(
    name="Sales Assistant",
    instructions="Help with sales tasks",
    functions=[get_customer_data, create_task],
)

databricks_agent = from_openai_swarm(
    swarm_agent,
    tracing={"destination": "main.default.traces"},
    conversation={"storage": "estore"},
)

databricks_agent.deploy()
```

**Key insight:** Adapters translate from other SDKs to our agent spec format, then run on our runtime. Degraded functionality is acceptable:
- ✅ Basic tool calling, streaming, conversation history
- ⚠️ Framework-specific features may not translate (e.g., LangChain's custom chains)
- ❌ Multi-user conversations, interrupts depend on framework support

---

## 3. Runtime: Agent Loop & Execution

### 3.1 Architecture: Leveraging MAS + aroll

The runtime builds on the existing **MAS (Multi-Agent Supervisor)** architecture, which uses **aroll** for async execution:

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime (MAS)                       │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Request Handler (handler.py)                        │   │
│  │  • Auth/session management                           │   │
│  │  • Load agent config                                 │   │
│  │  • Initialize conversation                           │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ↓                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Aroll Supervisor (supervisor_aroll.py)             │   │
│  │  • Agentic loop (think → act → observe)             │   │
│  │  • Tool orchestration                                │   │
│  │  • Streaming coordination                            │   │
│  │  • Error handling & retry                            │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     ↓                                         │
│  ┌────────────┬──────────────┬─────────────┬──────────┐   │
│  │ Tool:      │ Tool:        │ Tool:       │ Tool:    │   │
│  │ Genie      │ UC Function  │ MCP Server  │ Code Int │   │
│  └────────────┴──────────────┴─────────────┴──────────┘   │
│                     ↓                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Conversation Storage (estore / One Chat)           │   │
│  │  • Store messages, tool calls, results              │   │
│  │  • Auto-compaction on context overflow              │   │
│  └─────────────────────────────────────────────────────┘   │
│                     ↓                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Observability                                       │   │
│  │  • MLflow traces (spans for each step)              │   │
│  │  • UC table logging (tool calls, costs)             │   │
│  │  • Feedback collection (thumbs up/down)             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Loop State Machine

The agent loop follows a standard agentic pattern (enhanced from aroll):

```
┌──────────┐
│  START   │  User sends message
└────┬─────┘
     ↓
┌─────────────────────┐
│  LOAD CONTEXT       │  Load conversation history, agent config
└────┬────────────────┘
     ↓
┌─────────────────────┐
│  THINK              │  LLM generates response (may include tool calls)
└────┬────────────────┘
     ↓
     ├─→ [No tool calls] ──────────────────────────┐
     │                                              ↓
     └─→ [Tool calls requested]              ┌─────────────┐
           ↓                                  │  RESPOND    │  Stream final text
     ┌─────────────────────┐                 └──────┬──────┘
     │  APPROVE TOOLS      │  User approval          ↓
     │  (if policy=ask)    │  for state-changing   ┌─────────────┐
     └────┬────────────────┘  operations           │  SAVE       │  Save to conversation
          ↓                                         └──────┬──────┘
     ┌─────────────────────┐                              ↓
     │  EXECUTE TOOLS      │  Run in parallel        ┌─────────┐
     │  (parallel if       │  when possible          │  DONE   │
     │   supported)        │                         └─────────┘
     └────┬────────────────┘
          ↓
     ┌─────────────────────┐
     │  OBSERVE            │  Collect tool results
     └────┬────────────────┘
          ↓
          └──────────────→ [Loop back to THINK]
                          (if recursion_limit not reached)
```

### 3.3 Conversation Storage Integration

**Option 1: Leverage One Chat / estore (Recommended)**

MAS merged One Chat conversation storage (commit `467d6bf57c68e8cc641d48c2f0e55876e4082334`). Build on this:

```python
# Store conversation in estore
from kbqa.conversation.storage import ConversationStorage

storage = ConversationStorage(workspace_url=workspace_url)

# Create conversation
conversation_id = await storage.create_conversation(
    user_id=user.id,
    metadata={"agent": "sales_assistant", "app": "crm"},
)

# Add messages
await storage.add_message(
    conversation_id=conversation_id,
    role="user",
    content="Show me top customers",
)

# Retrieve history
messages = await storage.get_messages(
    conversation_id=conversation_id,
    limit=50,
)
```

**Option 2: Build Conversations API** (if estore insufficient)

Implement OpenAI-compatible Conversations API as specified in agentic-responses-api PRD:

```python
# POST /mlflow/v1/conversations
{
  "metadata": {
    "user_id": "sid.murching@databricks.com",
    "agent": "sales_assistant"
  },
  "items": [
    {"type": "message", "role": "user", "content": "Hello"}
  ]
}

# Response
{
  "id": "conv_abc123",
  "created_at": "2026-02-14T10:00:00Z",
  ...
}
```

### 3.4 Background Execution

For long-running workflows (e.g., deep research, multi-step analysis):

```yaml
# In agent invocation
POST /mlflow/v1/responses
{
  "model": "sales_assistant",
  "input": "Analyze all Q4 deals and create a summary report",
  "conversation": "conv_abc123",
  "background": true,  # Run in background
  "trace_destination": {
    "table": {"name": "main.sales.traces"}
  }
}

# Response (immediate)
{
  "id": "resp_def456",
  "status": "in_progress",
  "status_url": "/mlflow/v1/responses/resp_def456"
}

# Check status
GET /mlflow/v1/responses/resp_def456
{
  "id": "resp_def456",
  "status": "in_progress",  # or "completed", "failed"
  "progress": 0.6,  # Optional progress indicator
  "output": [...],  # Partial results (if available)
}

# Resume streaming (when user reconnects)
GET /mlflow/v1/responses/resp_def456?stream_after=100
# Streams from event 100 onwards
```

Implementation: Leverage aroll's checkpoint/resume capability + async task queue.

---

## 4. Agent Invocation API (OpenResponses++)

### 4.1 Base API: OpenResponses-Compatible

Follow the OpenResponses spec for the invocation API:

```
POST /mlflow/v1/responses
Content-Type: application/json

{
  "model": "sales_assistant",
  "input": "Show me top 10 customers by revenue",
  "conversation": "conv_abc123",  # Optional: continue conversation
  "stream": true,
  "temperature": 0.7,
  "max_output_tokens": 4096
}
```

**Streaming response** (Server-Sent Events):

```
event: response.created
data: {"id": "resp_123", "model": "sales_assistant", ...}

event: response.output_item.added
data: {"output_index": 0, "item": {"type": "message", "role": "assistant"}}

event: response.output_item.delta
data: {"output_index": 0, "delta": {"type": "output_text_delta", "text": "Let me"}}

event: response.output_item.delta
data: {"output_index": 0, "delta": {"type": "output_text_delta", "text": " query"}}

event: response.output_item.done
data: {"output_index": 0, "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Let me query the customer database."}]}}

event: response.output_item.added
data: {"output_index": 1, "item": {"type": "function_call", "name": "customer_data", "arguments": "{\"query\": \"SELECT * FROM customers ORDER BY revenue DESC LIMIT 10\"}"}}

# ... tool execution ...

event: response.output_item.added
data: {"output_index": 2, "item": {"type": "function_call_output", "content": "[{\"name\": \"Acme Corp\", \"revenue\": 1000000}, ...]"}}

event: response.output_item.added
data: {"output_index": 3, "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Here are the top 10 customers..."}]}}

event: response.done
data: {"id": "resp_123", "output": [...], "usage": {"input_tokens": 100, "output_tokens": 150}}
```

### 4.2 Extensions to OpenResponses

Implement extensions from `openresponses-spec-extensions.md`:

#### 4.2.1 Function Call Approval Request

```typescript
// When tool requires approval (approval_policy: always_ask)
{
  "type": "function_call_approval_request",
  "id": "approval_123",
  "call_id": "function_abc",
  "name": "create_crm_task",
  "arguments": "{\"title\": \"Follow up with Acme Corp\", \"assignee\": \"john@company.com\"}",
  "reason": "This will create a new task in your CRM",
  "options": [
    {"value": "approve", "label": "Allow this time"},
    {"value": "always_approve", "label": "Always allow (don't ask again)"},
    {"value": "deny", "label": "Deny"}
  ]
}

// User response (injected into conversation by frontend)
{
  "type": "function_call_approval_response",
  "approval_id": "approval_123",
  "decision": "approve"  // or "always_approve", "deny"
}
```

#### 4.2.2 OAuth Login Request

```typescript
// When tool requires OAuth (e.g., MCP server needs user creds)
{
  "type": "oauth_login_request",
  "id": "oauth_123",
  "provider": "salesforce",
  "login_url": "https://workspace.databricks.com/oauth/authorize?provider=salesforce&redirect=...",
  "reason": "Sign in to Salesforce to allow the agent to update records"
}

// After user completes OAuth, retry request automatically
```

#### 4.2.3 User Interruption

```typescript
// User interrupts ongoing execution
POST /mlflow/v1/responses/resp_123/interrupt
{
  "reason": "Look in the 'enterprise' CRM project instead"
}

// Agent receives interruption event and adjusts
{
  "type": "user_interruption",
  "id": "interrupt_123",
  "reason": "Look in the 'enterprise' CRM project instead"
}
```

#### 4.2.4 UI Content Rendering

```typescript
// Agent outputs custom UI (e.g., interactive chart)
{
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "output_text",
      "text": "Here is a revenue trend chart:"
    },
    {
      "type": "output_ui",
      "content": "[Revenue Chart]",  // Fallback text
      "ui": {
        "resource_uri": "ui://databricks/chart",
        "props": {
          "chart_type": "line",
          "data": [...],
          "x_axis": "month",
          "y_axis": "revenue"
        }
      }
    }
  ]
}
```

#### 4.2.5 Nested Sub-Agent Streams

```typescript
// Orchestrator agent calls sub-agent, streams nested output
{
  "type": "response.output_item.done",
  "output_index": 0,
  "item": {"type": "function_call", "name": "sub_agent", "call_id": "sub_xyz"}
}

// Nested stream from sub-agent
{
  "type": "response.nested.response.output_item.added",
  "parent_call_id": "sub_xyz",
  "output_index": 0,
  "item": {"type": "message", "role": "assistant", "content": [...]}
}

// Nested stream completes
{
  "type": "response.output_item.done",
  "output_index": 1,
  "item": {
    "type": "function_call_output",
    "call_id": "sub_xyz",
    "content": "Sub-agent completed task"
  }
}
```

### 4.3 Conversations API

Provide CRUDL operations for conversations:

```
# Create conversation
POST /mlflow/v1/conversations
{
  "metadata": {"user_id": "...", "agent": "sales_assistant"}
}

# List conversations
GET /mlflow/v1/conversations?limit=50&agent=sales_assistant

# Get conversation
GET /mlflow/v1/conversations/conv_abc123

# Delete conversation
DELETE /mlflow/v1/conversations/conv_abc123

# Add items to conversation (e.g., user message)
POST /mlflow/v1/conversations/conv_abc123/items
{
  "items": [
    {"type": "message", "role": "user", "content": "Hello"}
  ]
}
```

---

## 5. Conversation Management & Memory

### 5.1 Short-Term Memory (Conversation History)

**Storage:** Use One Chat / estore integration from MAS.

**Structure:**

```typescript
interface Conversation {
  id: string;  // conv_abc123
  user_id: string;
  agent_name: string;
  metadata: Record<string, any>;  // Custom app metadata
  created_at: string;
  updated_at: string;
}

interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: ContentBlock[];
  metadata: Record<string, any>;  // Feedback, cost, latency
  created_at: string;
}

interface ToolCall {
  id: string;
  message_id: string;  // Associated assistant message
  tool_name: string;
  arguments: string;  // JSON
  result: string;  // JSON
  status: 'pending' | 'approved' | 'denied' | 'completed' | 'failed';
  approval: {
    required: boolean;
    decision?: 'approve' | 'always_approve' | 'deny';
    timestamp?: string;
  };
  metadata: {
    duration_ms: number;
    cost_usd?: number;
  };
}
```

**Auto-Compaction:** When approaching LLM context limit:

```typescript
interface CompactionStrategy {
  type: 'summarize' | 'truncate' | 'hybrid';

  // For 'summarize': Generate summary of older messages
  summarize?: {
    llm: string;  // Model to use for summarization
    system_prompt: string;  // How to summarize
  };

  // For 'truncate': Remove oldest messages
  truncate?: {
    keep_recent: number;  // Keep last N messages
    keep_important: boolean;  // Keep flagged messages (e.g., user corrections)
  };
}
```

### 5.2 Long-Term Memory (Cross-Conversation)

**Future:** Enable agents to remember facts across conversations.

```yaml
# In agent.yaml
conversation:
  memory:
    long_term:
      enabled: true
      storage: main.sales.agent_memory

      # What to remember
      store:
        - type: user_preferences
          examples: ["User prefers concise responses", "User is a sales manager"]
        - type: domain_facts
          examples: ["Acme Corp is our biggest customer", "Q4 is our busiest season"]

      # Memory retrieval
      retrieval:
        strategy: semantic_search  # semantic_search | keyword | hybrid
        vector_search_index: main.sales.memory_index
        max_results: 5
```

**Implementation:**
1. After each conversation, extract key facts using LLM
2. Store in UC table with vector embeddings
3. On new conversation, retrieve relevant memories via vector search
4. Inject into system prompt: "Here's what I remember about you..."

### 5.3 Multi-User Conversations (Future)

Support multiple users in same conversation (e.g., team chat):

```typescript
interface Conversation {
  id: string;
  participant_ids: string[];  // Multiple users
  agent_name: string;
  access_control: {
    visibility: 'private' | 'shared' | 'public';
    allowed_users?: string[];
    allowed_groups?: string[];
  };
}

interface Message {
  id: string;
  conversation_id: string;
  author_id: string;  // Which user sent this
  role: 'user' | 'assistant';
  content: ContentBlock[];
  mentions?: string[];  // @username mentions
}
```

---

## 6. Frontend & UI Framework

### 6.1 Reference Implementation: e2e-chatbot-app-next

Provide a production-ready chat template (already exists):

**Features:**
- React + TypeScript frontend
- Vercel AI SDK for streaming
- Databricks authentication
- Conversation history sidebar
- Message feedback (thumbs up/down)
- Database integration (Lakebase)
- Databricks Asset Bundle deployment

**Usage:**
```bash
git clone https://github.com/databricks/app-templates
cd e2e-chatbot-app-next

# Configure
cp .env.example .env
# Set DATABRICKS_SERVING_ENDPOINT=your-agent-name

# Deploy
databricks bundle deploy
databricks bundle run databricks_chatbot
```

### 6.2 Customization Points

**1. Custom Message Rendering**

```typescript
// In client/src/components/elements/MessageRenderer.tsx
export function MessageRenderer({ message }: { message: Message }) {
  return message.content.map((block) => {
    switch (block.type) {
      case 'output_text':
        return <Markdown content={block.text} />;

      case 'output_ui':
        // Render custom UI (e.g., chart, table, map)
        return <CustomUIRenderer ui={block.ui} />;

      case 'output_image':
        return <img src={block.image_url} alt={block.alt_text} />;

      default:
        return <pre>{JSON.stringify(block, null, 2)}</pre>;
    }
  });
}
```

**2. Custom Input Components**

```typescript
// Add file upload, image input, etc.
export function ChatInput() {
  const [files, setFiles] = useState<File[]>([]);

  const handleSubmit = async () => {
    // Upload files to Volume
    const fileUrls = await uploadToVolume(files);

    // Send message with file references
    await sendMessage({
      role: 'user',
      content: [
        { type: 'input_text', text: userInput },
        ...fileUrls.map(url => ({ type: 'input_file', file_url: url })),
      ],
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <textarea value={userInput} onChange={...} />
      <FileUploader onFilesSelected={setFiles} />
      <button type="submit">Send</button>
    </form>
  );
}
```

**3. Branding & Styling**

```typescript
// Update theme in client/src/theme.ts
export const theme = {
  colors: {
    primary: '#FF3621',  // Your brand color
    background: '#FFFFFF',
    text: '#000000',
  },
  fonts: {
    body: 'Inter, sans-serif',
    heading: 'Poppins, sans-serif',
  },
};
```

### 6.3 Alternative UIs

**1. Document Editor with Inline Agent**

Similar to Notion AI or Cursor:

```typescript
// React component
export function DocumentEditorWithAgent() {
  const [document, setDocument] = useState<string>('');
  const [selection, setSelection] = useState<Range | null>(null);

  const handleAICommand = async (command: string) => {
    // Get selected text
    const selectedText = document.slice(selection.start, selection.end);

    // Call agent API
    const response = await fetch('/mlflow/v1/responses', {
      method: 'POST',
      body: JSON.stringify({
        model: 'writing_assistant',
        input: `${command}: ${selectedText}`,
        stream: true,
      }),
    });

    // Stream AI response and update document
    const reader = response.body.getReader();
    let aiText = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      aiText += new TextDecoder().decode(value);
      // Update document with AI-generated text
      setDocument(document.replace(selectedText, aiText));
    }
  };

  return (
    <div>
      <textarea value={document} onChange={...} onSelect={...} />
      <CommandPalette onCommand={handleAICommand} />
    </div>
  );
}
```

**2. Voice Interface (Future)**

Using Vercel AI SDK's multimodal support:

```typescript
import { useVoiceChat } from '@ai-sdk/react';

export function VoiceChatAgent() {
  const { startListening, stopListening, transcript, response } = useVoiceChat({
    api: '/mlflow/v1/responses',
    model: 'sales_assistant',
    voice: true,  # Enable voice I/O
  });

  return (
    <div>
      <button onMouseDown={startListening} onMouseUp={stopListening}>
        🎤 Hold to talk
      </button>
      <p>You: {transcript}</p>
      <p>Agent: {response}</p>
    </div>
  );
}
```

**3. Embedded in Other Apps (Future)**

Embed agent in Google Meet, Slack, Sheets, etc:

```typescript
// Chrome extension for embedding in any page
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'invoke_agent') {
    fetch('https://workspace.databricks.com/mlflow/v1/responses', {
      method: 'POST',
      body: JSON.stringify({
        model: 'meeting_assistant',
        input: request.context,  // Current page content, meeting transcript, etc.
      }),
    }).then(response => sendResponse(response));
  }
});
```

### 6.4 Vercel AI SDK Integration

The frontend already uses Vercel AI SDK, which now supports OpenResponses:

```typescript
import { useChat } from '@ai-sdk/react';

export function ChatInterface() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: '/mlflow/v1/responses',  // Our OpenResponses-compatible API
    body: {
      model: 'sales_assistant',
      conversation: conversationId,
    },
    onResponse: (response) => {
      // Handle custom events (tool approvals, OAuth, etc.)
      if (response.type === 'function_call_approval_request') {
        showApprovalModal(response);
      }
    },
  });

  return (
    <div>
      {messages.map(msg => <Message key={msg.id} message={msg} />)}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
```

---

## 7. Governance & Permissions

### 7.1 Permission Model

**Three levels of permissions:**

1. **Agent-level:** Who can invoke this agent?
2. **Tool-level:** Who can use each tool? Execute on behalf of user or as service principal?
3. **Conversation-level:** Who can read/write this conversation?

### 7.2 Agent-Level Permissions

```yaml
# In agent.yaml
governance:
  allowed_principals:
    - users  # All workspace users
    - groups: ["sales_team", "customer_success"]
    - service_principals: ["crm_integration_sp"]

  denied_principals:
    - users: ["blocked_user@company.com"]
```

**Enforcement:** API checks caller's identity against allowed/denied lists before executing agent.

### 7.3 Tool-Level Permissions

```yaml
tools:
  - type: table
    name: customer_data
    table_name: main.sales.customers

    # Execute with user's UC permissions (respects RLS, column masking, etc.)
    permission: on_behalf_of_user

    # Require approval before executing
    approval_policy: always_ask  # always_allow | always_ask | smart
```

**Permission modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `on_behalf_of_user` | Execute with user's identity and permissions | Read user's private data, respect RLS |
| `as_service_principal` | Execute with agent's service principal | Read public data, write to shared tables |

**Approval policies:**

| Policy | Description | When to Use |
|--------|-------------|-------------|
| `always_allow` | Never ask for approval | Safe read-only operations (query table, search) |
| `always_ask` | Always ask for approval | State-changing operations (create task, send email) |
| `smart` | Ask only for state-changing ops | Auto-detect based on tool semantics |

### 7.4 Conversation-Level Permissions

**Option 1: User-Owned Conversations**

Default mode: Each conversation is owned by the user who created it.

```typescript
interface Conversation {
  id: string;
  owner_id: string;  // User who created it
  access_control: {
    visibility: 'private',  // Only owner can access
  };
}
```

**Option 2: App-Mediated Conversations** (for multi-user apps)

Use service principal as owner, app backend controls access:

```typescript
interface Conversation {
  id: string;
  owner_id: string;  // Service principal (app)
  access_control: {
    visibility: 'shared',
    allowed_users: ['alice@company.com', 'bob@company.com'],
  };
}

// App backend validates access before allowing operations
async function getConversation(conversationId: string, userId: string) {
  const conv = await db.getConversation(conversationId);
  if (!conv.access_control.allowed_users.includes(userId)) {
    throw new Error('Unauthorized');
  }
  return conv;
}
```

### 7.5 Resource Limits & Guardrails

```yaml
governance:
  # Cost limits
  max_cost_per_session: 0.50  # Max $0.50 per conversation
  max_cost_per_user_per_day: 5.00  # Max $5 per user per day

  # Time limits
  max_duration_seconds: 300  # Max 5 minutes per response
  max_background_duration_seconds: 3600  # Max 1 hour for background mode

  # Rate limits
  rate_limit:
    requests_per_minute: 60
    requests_per_hour: 500
    requests_per_day: 5000

  # Content safety
  content_safety:
    enabled: true
    block_pii_in_traces: true  # Redact PII from MLflow traces
    block_toxic_content: true  # Filter toxic user inputs
```

**Enforcement:** Runtime monitors usage and throws errors when limits exceeded.

### 7.6 Admin Policies (Workspace-Level)

Workspace admins can set policies that apply to ALL agents:

```yaml
# Workspace-level policy (set via Databricks admin console)
workspace_policies:
  # Prevent agents from accessing certain tables
  denied_tables:
    - main.hr.salaries
    - main.finance.bank_accounts

  # Require approval for all external MCP calls
  require_approval_for_external_tools: true

  # Block certain LLM providers
  allowed_providers: ["databricks", "openai"]
  denied_providers: ["anthropic"]  # Example: compliance reasons
```

---

## 8. Observability & Feedback

### 8.1 Tracing with MLflow

Every agent execution generates an MLflow trace:

```yaml
# In agent.yaml
tracing:
  enabled: true
  destination:
    type: table  # or "mlflow_experiment"
    name: main.sales.agent_traces

  # What to include
  include_tool_inputs: true
  include_tool_outputs: true
  include_prompt: true
  include_completions: true

  # Privacy
  redact_pii: true  # Automatically redact PII (emails, SSNs, etc.)
```

**Trace schema:**

```sql
CREATE TABLE main.sales.agent_traces (
  trace_id STRING,
  conversation_id STRING,
  agent_name STRING,
  user_id STRING,
  timestamp TIMESTAMP,

  -- Request/response
  input STRING,  -- User message
  output STRING,  -- Agent response

  -- Execution
  duration_ms BIGINT,
  status STRING,  -- 'completed', 'failed', 'interrupted'
  error STRING,  -- Error message (if failed)

  -- LLM usage
  llm_calls ARRAY<STRUCT<
    model STRING,
    input_tokens INT,
    output_tokens INT,
    duration_ms BIGINT,
    cost_usd DOUBLE
  >>,

  -- Tool usage
  tool_calls ARRAY<STRUCT<
    tool_name STRING,
    arguments STRING,
    result STRING,
    duration_ms BIGINT,
    status STRING,  -- 'completed', 'failed', 'denied'
    approval_required BOOLEAN,
    approval_decision STRING
  >>,

  -- Cost
  total_cost_usd DOUBLE,

  -- Metadata
  metadata MAP<STRING, STRING>
);
```

**Querying traces:**

```sql
-- Find slowest agent calls
SELECT agent_name, AVG(duration_ms) as avg_duration
FROM main.sales.agent_traces
WHERE timestamp > NOW() - INTERVAL 7 DAYS
GROUP BY agent_name
ORDER BY avg_duration DESC;

-- Find most expensive tool calls
SELECT
  tool_name,
  COUNT(*) as num_calls,
  SUM(cost_usd) as total_cost
FROM main.sales.agent_traces
LATERAL VIEW explode(tool_calls) as tool
GROUP BY tool_name
ORDER BY total_cost DESC;

-- Find failed executions
SELECT trace_id, agent_name, error
FROM main.sales.agent_traces
WHERE status = 'failed'
ORDER BY timestamp DESC
LIMIT 10;
```

### 8.2 Feedback Collection

```yaml
# In agent.yaml
feedback:
  enabled: true
  destination:
    type: table
    name: main.sales.agent_feedback

  # Feedback types to collect
  types:
    - thumbs_up_down
    - rating_1_to_5
    - free_text_comment
```

**Frontend integration:**

```typescript
// In chat UI
export function Message({ message }: { message: Message }) {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleFeedback = async (value: 'up' | 'down') => {
    setFeedback(value);
    await fetch('/mlflow/v1/feedback', {
      method: 'POST',
      body: JSON.stringify({
        message_id: message.id,
        conversation_id: message.conversation_id,
        feedback_type: 'thumbs',
        feedback_value: value,
      }),
    });
  };

  return (
    <div>
      <MessageContent content={message.content} />
      <div className="feedback">
        <button onClick={() => handleFeedback('up')}>👍</button>
        <button onClick={() => handleFeedback('down')}>👎</button>
      </div>
    </div>
  );
}
```

**Feedback schema:**

```sql
CREATE TABLE main.sales.agent_feedback (
  feedback_id STRING,
  message_id STRING,
  conversation_id STRING,
  trace_id STRING,
  user_id STRING,
  timestamp TIMESTAMP,

  -- Feedback
  feedback_type STRING,  -- 'thumbs', 'rating', 'comment'
  feedback_value STRING,  -- 'up'/'down', '1-5', or free text

  -- Context
  agent_name STRING,
  tool_calls ARRAY<STRING>,  -- Tools used in this response

  -- Metadata
  metadata MAP<STRING, STRING>
);
```

### 8.3 Auto-Evaluation with Judges

Use LLM-as-a-judge to automatically evaluate agent responses:

```yaml
# In agent.yaml (optional)
evaluation:
  enabled: true
  judges:
    - name: helpfulness
      prompt: |
        Rate how helpful this response is on a scale of 1-5.
        Consider: accuracy, relevance, completeness.
      model: databricks-claude-sonnet-4-5

    - name: safety
      prompt: |
        Does this response contain any harmful or biased content?
        Answer: yes or no.
      model: databricks-claude-sonnet-4-5

  # Store judge results in traces table
  store_in_traces: true
```

**Judge results in traces:**

```sql
SELECT
  trace_id,
  output,
  metadata['judge_helpfulness'] as helpfulness,
  metadata['judge_safety'] as safety
FROM main.sales.agent_traces
WHERE metadata['judge_safety'] = 'no'
ORDER BY CAST(metadata['judge_helpfulness'] AS INT) DESC;
```

### 8.4 Dashboards & Monitoring

Provide pre-built dashboards for monitoring agents:

**1. Agent Performance Dashboard**
- Requests per hour/day
- Average latency (p50, p95, p99)
- Error rate
- Cost per request
- Most used tools

**2. User Engagement Dashboard**
- Active users
- Messages per user
- Conversation length distribution
- Feedback score distribution
- Retention (users returning 7/30 days later)

**3. Tool Usage Dashboard**
- Tool call frequency
- Tool call latency
- Tool approval rate (% of calls requiring approval)
- Tool failure rate

---

## 9. Implementation Phases

### Phase 0: Foundation (Weeks 1-2)
**Goal:** Set up core infrastructure

**Tasks:**
- [ ] Create agent spec schema (YAML format)
- [ ] Extend aroll config parser to support agent spec
- [ ] Set up agent registry (UC catalog for storing agent configs)
- [ ] Basic API endpoint: `POST /mlflow/v1/responses` (no tools yet)
- [ ] Integrate One Chat conversation storage

**Deliverables:**
- Agent spec documentation
- Basic agent deployment via `databricks bundle deploy`
- Simple echo agent (no tools)

### Phase 1: Tool Calling (Weeks 3-6)
**Goal:** Enable agents to call tools

**Tasks:**
- [ ] Implement UC table tool (query on behalf of user)
- [ ] Implement Genie tool (existing MAS integration)
- [ ] Implement UC function tool
- [ ] Implement MCP tool (external servers)
- [ ] Add tool approval flow (function_call_approval_request/response)
- [ ] Parallel tool execution (aroll already supports)
- [ ] Streaming with tool calls (OpenResponses format)

**Deliverables:**
- Agent with 2+ tools working end-to-end
- Chat UI showing tool approvals
- Example: "Sales Assistant" agent (Genie + UC function + MCP)

### Phase 2: Conversation Management (Weeks 7-9)
**Goal:** Persistent conversations

**Tasks:**
- [ ] Conversations API (CRUDL endpoints)
- [ ] Conversation auto-compaction (when approaching context limit)
- [ ] Conversation list in chat UI
- [ ] Multi-conversation support (switch between conversations)
- [ ] Conversation metadata & search

**Deliverables:**
- Full conversation persistence
- Chat history sidebar in UI
- Conversation search by metadata

### Phase 3: Observability & Feedback (Weeks 10-12)
**Goal:** Production-ready monitoring

**Tasks:**
- [ ] MLflow trace integration (spans for each step)
- [ ] UC table logging (alternative to MLflow experiments)
- [ ] Feedback collection (thumbs up/down in UI)
- [ ] Feedback API endpoints
- [ ] Pre-built dashboards (agent performance, user engagement, tool usage)
- [ ] Cost tracking per agent/user/conversation

**Deliverables:**
- Full trace logging to UC table
- Feedback collection working in UI
- 3 pre-built dashboards

### Phase 4: Governance & Permissions (Weeks 13-15)
**Goal:** Enterprise-grade governance

**Tasks:**
- [ ] Agent-level permissions (who can invoke)
- [ ] Tool-level permissions (on_behalf_of_user vs as_service_principal)
- [ ] Resource limits (cost, time, rate limits)
- [ ] Content safety (PII redaction, toxic content filtering)
- [ ] Admin policies (workspace-level rules)
- [ ] Audit logging (who invoked what, when)

**Deliverables:**
- Full governance model implemented
- Admin console for setting policies
- Compliance documentation

### Phase 5: Advanced Features (Weeks 16-20)
**Goal:** Differentiated capabilities

**Tasks:**
- [ ] Background/long-running execution
- [ ] User interruptions (pause/steer agent)
- [ ] Long-term memory (cross-conversation)
- [ ] Auto-evaluation with judges
- [ ] Code interpreter tool (built-in)
- [ ] Web search tool (built-in)
- [ ] Multi-user conversations (future)
- [ ] Voice interface (future)

**Deliverables:**
- Background mode working (up to 1 hour executions)
- Interrupt/steer UX in chat UI
- Long-term memory for 1+ agents

### Phase 6: SDK & Ecosystem (Weeks 21-24)
**Goal:** Developer ecosystem

**Tasks:**
- [ ] TypeScript SDK (@databricks/agent-framework)
- [ ] Python SDK (databricks-agent-framework)
- [ ] Adapters for other SDKs (LangChain, OpenAI, CrewAI)
- [ ] Visual agent builder (drag-and-drop UI)
- [ ] Agent marketplace (share/discover agents)
- [ ] VS Code extension (build agents in IDE)
- [ ] Agent testing framework (unit tests for agents)

**Deliverables:**
- Full TypeScript & Python SDKs
- 3+ framework adapters (LangChain, OpenAI, CrewAI)
- Visual builder MVP

---

## 10. Examples & Use Cases

### Example 1: Sales Assistant

```yaml
name: sales_assistant
description: "Helps sales reps find customer data and create tasks"

model:
  provider: databricks
  name: databricks-claude-sonnet-4-5
  temperature: 0.7

prompt:
  system: |
    You are a sales assistant at Acme Corp.
    Help sales reps find customer information, analyze deals, and create follow-up tasks.
    Always cite your sources when referencing data.

tools:
  - type: table
    name: customer_data
    description: "Query customer profiles and purchase history"
    table_name: main.sales.customers
    permission: on_behalf_of_user
    approval_policy: always_allow

  - type: genie
    name: revenue_analyst
    description: "Analyze revenue trends"
    space_id: "01f0695490611f89bba0a496dbdd840c"
    permission: on_behalf_of_user
    approval_policy: always_allow

  - type: uc_function
    name: create_task
    description: "Create CRM task"
    function_name: main.sales.create_crm_task
    permission: on_behalf_of_user
    approval_policy: always_ask

tracing:
  enabled: true
  destination:
    type: table
    name: main.sales.agent_traces

feedback:
  enabled: true
  destination:
    type: table
    name: main.sales.agent_feedback
```

**Usage:**
```bash
databricks bundle deploy
databricks bundle run sales_assistant

# Chat UI at https://workspace.databricks.com/apps/sales-assistant
```

### Example 2: HR Support Agent

```yaml
name: hr_support
description: "Answers employee questions about benefits, PTO, and policies"

model:
  provider: databricks
  name: databricks-gpt-5-2
  temperature: 0.5

prompt:
  system: |
    You are an HR support agent for Acme Corp.
    Help employees with questions about benefits, PTO, policies, and more.
    Be empathetic and professional.
    If you don't know the answer, direct them to hr@company.com.

tools:
  - type: table
    name: employee_data
    description: "Query employee profiles (RLS applied automatically)"
    table_name: main.hr.employees
    permission: on_behalf_of_user  # Respects RLS, user can only see their own data
    approval_policy: always_allow

  - type: uc_function
    name: calculate_pto_balance
    description: "Calculate remaining PTO days"
    function_name: main.hr.calculate_pto
    permission: on_behalf_of_user
    approval_policy: always_allow

  - type: agent_endpoint
    name: policy_search
    description: "Search company policy documents"
    endpoint_name: hr_policy_knowledge_agent
    permission: as_service_principal  # Policies are public
    approval_policy: always_allow

conversation:
  auto_compact: true
  compact_strategy: summarize

governance:
  allowed_principals:
    - users  # All employees can access
  max_cost_per_session: 0.25
```

### Example 3: Code Review Agent

```yaml
name: code_reviewer
description: "Reviews code changes and provides feedback"

model:
  provider: databricks
  name: databricks-claude-sonnet-4-5
  temperature: 0.3

prompt:
  system: |
    You are a code review assistant.
    Review code for:
    - Correctness
    - Performance
    - Security issues
    - Best practices
    Provide specific, actionable feedback.

tools:
  - type: mcp
    name: github
    description: "Access GitHub PRs and files"
    connection_name: github_prod
    permission: on_behalf_of_user
    approval_policy: always_ask  # Ask before commenting on PR

  - type: code_interpreter
    name: static_analysis
    description: "Run linters and static analysis"
    approval_policy: always_allow

  - type: uc_function
    name: search_codebase
    description: "Search codebase for similar patterns"
    function_name: main.eng.search_code
    permission: as_service_principal
    approval_policy: always_allow

behavior:
  recursion_limit: 15  # May need multiple steps to review
  parallel_tools: true

tracing:
  enabled: true
  destination:
    type: table
    name: main.eng.code_review_traces
```

**Integration with GitHub:**
```typescript
// GitHub App webhook handler
app.post('/webhooks/github', async (req, res) => {
  const { action, pull_request } = req.body;

  if (action === 'opened' || action === 'synchronize') {
    // Invoke code review agent
    await fetch('https://workspace.databricks.com/mlflow/v1/responses', {
      method: 'POST',
      body: JSON.stringify({
        model: 'code_reviewer',
        input: `Review PR #${pull_request.number}: ${pull_request.title}`,
        background: true,  // Run in background (may take a while)
      }),
    });
  }

  res.status(200).send('OK');
});
```

### Example 4: Data Analysis Agent

```yaml
name: data_analyst
description: "Answers data questions using SQL and Python"

model:
  provider: databricks
  name: databricks-claude-sonnet-4-5
  temperature: 0.7

prompt:
  system: |
    You are a data analyst.
    Help users answer questions about their data.
    Write SQL queries to explore data, then analyze results with Python.
    Create visualizations when appropriate.

tools:
  - type: table
    name: sales_data
    description: "Sales transactions"
    table_name: main.analytics.sales
    permission: on_behalf_of_user
    approval_policy: always_allow

  - type: table
    name: customer_data
    description: "Customer profiles"
    table_name: main.analytics.customers
    permission: on_behalf_of_user
    approval_policy: always_allow

  - type: code_interpreter
    name: python_analysis
    description: "Analyze data with Python (pandas, matplotlib, seaborn)"
    approval_policy: always_allow

behavior:
  recursion_limit: 10
  parallel_tools: false  # Sequential: query first, then analyze

# Output custom UI (charts)
ui:
  enable_custom_rendering: true
  supported_types:
    - chart
    - table
    - map
```

**Usage in UI:**
```typescript
// Render custom chart output
export function MessageRenderer({ message }: { message: Message }) {
  return message.content.map((block) => {
    if (block.type === 'output_ui' && block.ui.type === 'chart') {
      return (
        <Chart
          type={block.ui.props.chart_type}
          data={block.ui.props.data}
          xAxis={block.ui.props.x_axis}
          yAxis={block.ui.props.y_axis}
        />
      );
    }
    return <Markdown content={block.text} />;
  });
}
```

---

## Appendix A: Agent Spec JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "model", "tools"],
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9_]{0,63}$",
      "description": "Agent identifier (lowercase, alphanumeric, underscores)"
    },
    "version": {
      "type": "string",
      "description": "Agent version (semver)"
    },
    "description": {
      "type": "string",
      "description": "Human-readable description"
    },
    "model": {
      "type": "object",
      "required": ["provider", "name"],
      "properties": {
        "provider": {
          "enum": ["databricks", "openai", "anthropic", "custom"]
        },
        "name": {
          "type": "string",
          "description": "Model name (e.g., databricks-claude-sonnet-4-5)"
        },
        "temperature": {
          "type": "number",
          "minimum": 0,
          "maximum": 2
        },
        "max_output_tokens": {
          "type": "integer",
          "minimum": 1
        }
      }
    },
    "prompt": {
      "type": "object",
      "properties": {
        "system": {
          "type": "string",
          "description": "System prompt"
        },
        "user": {
          "type": "object",
          "properties": {
            "mode": {
              "enum": ["prepend", "append", "replace"]
            },
            "prompt": {
              "type": "string"
            }
          }
        }
      }
    },
    "tools": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "name", "description"],
        "properties": {
          "type": {
            "enum": ["table", "genie", "uc_function", "mcp", "web_search", "code_interpreter", "agent_endpoint", "custom"]
          },
          "name": {
            "type": "string"
          },
          "description": {
            "type": "string"
          },
          "permission": {
            "enum": ["on_behalf_of_user", "as_service_principal"]
          },
          "approval_policy": {
            "enum": ["always_allow", "always_ask", "smart"]
          }
        }
      }
    },
    "behavior": {
      "type": "object",
      "properties": {
        "recursion_limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50
        },
        "parallel_tools": {
          "type": "boolean"
        },
        "streaming": {
          "type": "boolean"
        }
      }
    },
    "conversation": {
      "type": "object",
      "properties": {
        "auto_compact": {
          "type": "boolean"
        },
        "compact_strategy": {
          "enum": ["summarize", "truncate", "hybrid"]
        }
      }
    },
    "tracing": {
      "type": "object",
      "properties": {
        "enabled": {
          "type": "boolean"
        },
        "destination": {
          "type": "object",
          "properties": {
            "type": {
              "enum": ["table", "mlflow_experiment"]
            },
            "name": {
              "type": "string"
            }
          }
        }
      }
    },
    "governance": {
      "type": "object",
      "properties": {
        "max_cost_per_session": {
          "type": "number",
          "minimum": 0
        },
        "max_duration_seconds": {
          "type": "integer",
          "minimum": 1
        },
        "allowed_principals": {
          "type": "array"
        }
      }
    }
  }
}
```

---

## Appendix B: OpenResponses Event Types Summary

| Event Type | Description | When Emitted |
|------------|-------------|--------------|
| `response.created` | Response started | Immediately after request |
| `response.output_item.added` | New item added to output | When agent starts new message/tool call |
| `response.output_item.delta` | Incremental update to item | During streaming text generation |
| `response.output_item.updated` | Full replacement of item | For ephemeral status updates |
| `response.output_item.done` | Item completed | When message/tool call finishes |
| `response.done` | Response completed | End of agent execution |
| `response.failed` | Response failed | On error |
| `response.interrupted` | User interrupted | User cancels execution |
| `function_call_approval_request` | Tool requires approval | Tool with `approval_policy: always_ask` |
| `function_call_approval_response` | User approved/denied tool | User responds to approval request |
| `oauth_login_request` | Tool requires OAuth | MCP tool needs user auth |
| `user_interruption` | User steers agent | User interrupts with new guidance |
| `response.nested.response.*` | Sub-agent stream | Orchestrator calls sub-agent |

---

## Appendix C: Comparison with Other Frameworks

| Feature | Our Framework | LangChain | OpenAI Agents SDK | CrewAI |
|---------|--------------|-----------|------------------|--------|
| **Declarative YAML** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Multi-provider** | ✅ OpenAI, Claude, custom | ✅ Many | ❌ OpenAI only | ✅ Many |
| **Conversation storage** | ✅ Built-in (estore) | ❌ DIY | ✅ Built-in | ❌ DIY |
| **Tracing** | ✅ MLflow + UC tables | ✅ LangSmith | ✅ Built-in | ❌ DIY |
| **Tool approval UX** | ✅ Built-in | ❌ DIY | ✅ Built-in | ❌ DIY |
| **Background execution** | ✅ Built-in | ❌ DIY | ❌ No | ❌ DIY |
| **Databricks tools** | ✅ UC tables, Genie, etc. | ⚠️ Via custom tools | ⚠️ Via custom tools | ⚠️ Via custom tools |
| **Governance** | ✅ Built-in | ❌ DIY | ⚠️ Partial | ❌ DIY |
| **UI templates** | ✅ Chat, docs, voice | ❌ No | ⚠️ Basic chat | ❌ No |
| **Portability** | ✅ Import from others | N/A | N/A | N/A |

**Key differentiators:**
1. **Databricks-native**: Deep UC integration, Genie, on-behalf-of-user execution
2. **Declarative-first**: YAML for most use cases, SDK for advanced
3. **Production-ready**: Observability, governance, feedback built-in from day 1
4. **Interoperable**: Import agents from other SDKs, OpenResponses-compatible API

---

## Appendix D: Migration Paths

### From LangChain

```python
# Before: LangChain agent
from langchain.agents import create_react_agent
from langchain.tools import Tool

tools = [
    Tool(name="Search", func=search_func, description="Search the web"),
    Tool(name="Calculator", func=calc_func, description="Calculate math"),
]

agent = create_react_agent(llm=llm, tools=tools, prompt=prompt_template)

# After: Our framework (YAML)
# agent.yaml
name: my_agent
model:
  provider: databricks
  name: databricks-claude-sonnet-4-5

tools:
  - type: web_search
    name: search
    description: "Search the web"
  - type: uc_function
    name: calculator
    function_name: main.tools.calculate

# Or: Import with adapter
from databricks.agent_framework.adapters import from_langchain

databricks_agent = from_langchain(agent)
databricks_agent.deploy()
```

### From OpenAI Agents SDK

```typescript
// Before: OpenAI agent
const agent = new Agent({
  name: 'My Agent',
  instructions: 'You are a helpful assistant',
  tools: [searchTool, calculatorTool],
  model: 'gpt-4',
});

// After: Our framework (YAML)
// agent.yaml
name: my_agent
model:
  provider: openai
  name: gpt-4
prompt:
  system: "You are a helpful assistant"
tools:
  - type: web_search
    name: search
  - type: uc_function
    name: calculator
    function_name: main.tools.calculate

// Or: Import with adapter
import { fromOpenAI } from '@databricks/agent-framework/adapters';

const databricksAgent = fromOpenAI(agent, {
  tracing: { destination: 'main.default.traces' },
});
await databricksAgent.deploy();
```

---

## Appendix E: Open Questions & Future Work

### Open Questions

1. **Conversation storage:** Use One Chat/estore or build separate Conversations API?
   - **Recommendation:** Start with estore (already integrated), add Conversations API in Phase 2 if needed

2. **Billing model:** Charge for FMAPI usage + tool costs, or abstract into "agent credits"?
   - **Recommendation:** Start with transparent FMAPI + tool billing, revisit for PuPr

3. **Multi-tenancy:** Allow shared database instances for multiple agents or one DB per agent?
   - **Recommendation:** One DB per agent for Phase 1 (simpler), explore shared instances in Phase 6

4. **Visual builder:** Web-based or VS Code extension?
   - **Recommendation:** Web-based (lower friction), VS Code extension as add-on

5. **Voice/multimodal:** Wait for Vercel AI SDK support or build custom?
   - **Recommendation:** Wait for Vercel AI SDK (Phase 5), POC with Web Speech API in meantime

### Future Work (Beyond Phase 6)

- **Agent composition:** Orchestrator agents that call multiple sub-agents
- **Agent marketplace:** Public registry of pre-built agents
- **Agent templates:** Cookiecutter-style templates for common use cases
- **Agent testing framework:** Unit tests, integration tests, load tests for agents
- **Agent versioning:** Deploy multiple versions, canary/blue-green deployments
- **Agent monitoring:** Anomaly detection, drift detection, auto-scaling
- **Agent collaboration:** Multiple agents working together on same task
- **Human-in-the-loop:** Agents that pause and ask for human input mid-execution
- **Agentic workflows:** Multi-step workflows triggered by events (cron, webhooks, etc.)
- **Agent fine-tuning:** Fine-tune models on agent's conversation history

---

## Appendix F: Success Metrics

| Metric | Target (6 months) | Measurement |
|--------|------------------|-------------|
| **Adoption** |
| Active agents | 100+ | Agents with >10 invocations/week |
| Agent creators | 50+ | Unique users who deployed agents |
| Total invocations | 100K+ | Across all agents |
| **Quality** |
| Avg feedback score | 4.0/5.0 | Thumbs up/down converted to 1-5 scale |
| Success rate | >95% | % of invocations without errors |
| Avg latency (p95) | <5s | Excluding background mode |
| **Ecosystem** |
| SDK downloads | 1K+ | npm + PyPI downloads |
| Community agents | 10+ | Agents shared in marketplace |
| Documentation views | 10K+ | Unique page views on docs site |

---

## Appendix G: References

**Internal Docs:**
- [aroll README](~/universe/research/aroll/README.md)
- [MAS README](~/universe/agentbricks/mas/README.md)
- [e2e-chatbot-app-next README](~/app-templates/e2e-chatbot-app-next/README.md)
- [Agentic Responses API PRD](~/agentic-responses-api/agentic-responses-api-prd.md)

**External Specs:**
- [OpenResponses Spec](https://www.openresponses.org/specification)
- [OpenAI Agents API](https://platform.openai.com/docs/api-reference/agents)
- [Anthropic MCP Protocol](https://modelcontextprotocol.io/docs)
- [Vercel AI SDK](https://sdk.vercel.ai/docs)

**Competitive:**
- [LangChain](https://python.langchain.com/docs/get_started/introduction)
- [CrewAI](https://docs.crewai.com/)
- [OpenAI Swarm](https://github.com/openai/swarm)
- [Claude Artifacts](https://support.anthropic.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)

---

**End of Specification**
