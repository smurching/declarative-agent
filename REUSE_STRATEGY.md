# Component Reuse Strategy for Declarative Agent Framework

**Date:** February 14, 2026

This document outlines how we can leverage existing components to accelerate development of the declarative agent framework, maximizing reuse and minimizing new development.

## Component Mapping: Existing → Framework

### 1. aroll (~/universe/research/aroll)

**What it provides:**
- ✅ YAML-based agent configuration
- ✅ Async-first execution engine
- ✅ Multi-provider LLM support (OpenAI, Claude, Databricks, etc.)
- ✅ Built-in tool execution and parallel tool calling
- ✅ Plugin system for context management
- ✅ MLflow tracing integration
- ✅ Auto-resumption on failures
- ✅ Reward system for evaluation

**How we'll use it:**
- **Core runtime engine:** aroll becomes the foundation of our agent execution layer
- **Configuration parser:** Extend aroll's YAML parser to support our agent spec
- **Tool orchestration:** Leverage aroll's existing tool execution logic
- **Trace logging:** Use aroll's MLflow integration out of the box

**Extensions needed:**
```yaml
# Extend aroll config to support our agent spec
env:
  # NEW: Agent metadata
  agent:
    name: sales_assistant
    version: 1.0
    description: "Helps sales reps"

  # NEW: Per-tool permissions
  tools:
    - name: customer_data
      type: databricks_table
      table_name: main.sales.customers
      permission: on_behalf_of_user  # NEW FIELD
      approval_policy: always_allow  # NEW FIELD

  # NEW: Governance
  governance:
    max_cost_per_session: 0.50
    max_duration_seconds: 300

  # EXISTING: Rest of aroll config (prompt, llm, etc.)
  prompt: { ... }
  llm_endpoint_name: databricks-claude-sonnet-4-5
```

**Development effort:** ~2 weeks to extend config schema and add governance

---

### 2. MAS - Multi-Agent Supervisor (~/universe/agentbricks/mas)

**What it provides:**
- ✅ HTTP request handler for agent invocations
- ✅ Aroll-based supervisor loop
- ✅ Tool coordination (Genie, UC Functions, MCP servers, Knowledge Agents)
- ✅ Streaming response architecture
- ✅ Session management
- ✅ OpenResponses-like API format
- ✅ One Chat conversation storage integration (commit 467d6bf)

**How we'll use it:**
- **API endpoint:** MAS's `/api/2.0/mas/invocations` becomes our `/mlflow/v1/responses`
- **Agent loop:** Use MAS's supervisor_aroll.py as base
- **Tool registry:** Extend MAS's tool types (Genie, UC Function, MCP, etc.)
- **Conversation storage:** Leverage MAS's estore integration

**Extensions needed:**
```python
# In mas/python/agent/supervisor_aroll.py

class SupervisorAroll:
    def __init__(self, config: AgentConfig, workspace: Workspace):
        # EXISTING: Load aroll config
        self.aroll_env = load_aroll_config(config.aroll_yaml)

        # NEW: Load agent spec
        self.agent_spec = AgentSpec.from_yaml(config.agent_yaml)

        # NEW: Initialize governance
        self.governance = GovernanceManager(
            max_cost=self.agent_spec.governance.max_cost_per_session,
            max_duration=self.agent_spec.governance.max_duration_seconds,
        )

        # NEW: Tool approval manager
        self.approval_manager = ToolApprovalManager(
            policies={tool.name: tool.approval_policy for tool in self.agent_spec.tools}
        )

    async def predict(self, request: PredictRequest):
        # EXISTING: Check session, load history
        # EXISTING: Execute aroll loop
        # NEW: Emit OpenResponses events (instead of current format)
        # NEW: Handle tool approvals
        # NEW: Track cost/duration, enforce limits
```

**Development effort:** ~3-4 weeks to add governance, tool approvals, and full OpenResponses compliance

---

### 3. e2e-chatbot-app-next (~/app-templates/e2e-chatbot-app-next)

**What it provides:**
- ✅ Production-ready React chat UI
- ✅ Vercel AI SDK integration for streaming
- ✅ Express.js backend
- ✅ Databricks authentication (CLI + service principal)
- ✅ Conversation history sidebar
- ✅ Message feedback (thumbs up/down)
- ✅ Database integration (Lakebase/Postgres)
- ✅ Databricks Asset Bundle deployment
- ✅ E2E tests with Playwright

**How we'll use it:**
- **Reference implementation:** This becomes our official chat UI template
- **Streaming client:** Vercel AI SDK already supports OpenResponses (per their docs)
- **Feedback collection:** Use existing thumbs up/down UI, wire to our Feedback API
- **Deployment:** Use DAB pattern for deploying agent + UI together

**Extensions needed:**
```typescript
// In client/src/components/elements/MessageRenderer.tsx

export function MessageRenderer({ message }: { message: Message }) {
  return message.content.map((block) => {
    switch (block.type) {
      case 'output_text':
        return <Markdown content={block.text} />;

      // NEW: Handle tool approval requests
      case 'function_call_approval_request':
        return (
          <ToolApprovalCard
            toolName={block.name}
            arguments={block.arguments}
            reason={block.reason}
            onApprove={() => handleApproval(block.id, 'approve')}
            onDeny={() => handleApproval(block.id, 'deny')}
          />
        );

      // NEW: Handle OAuth login requests
      case 'oauth_login_request':
        return (
          <OAuthLoginCard
            provider={block.provider}
            loginUrl={block.login_url}
            reason={block.reason}
          />
        );

      // NEW: Handle custom UI rendering
      case 'output_ui':
        return <CustomUIRenderer ui={block.ui} />;

      // EXISTING: Other content types
      default:
        return <pre>{JSON.stringify(block, null, 2)}</pre>;
    }
  });
}
```

**Development effort:** ~2 weeks to add tool approvals, OAuth, and custom UI rendering

---

### 4. OpenResponses Spec (~/openresponses)

**What it provides:**
- ✅ Standard API schema for agent invocation
- ✅ Streaming event types
- ✅ Compliance tests
- ✅ Multi-provider compatibility

**How we'll use it:**
- **API spec:** Our `/mlflow/v1/responses` API strictly follows OpenResponses
- **Event format:** Use OpenResponses streaming events
- **Compliance:** Run OpenResponses compliance tests against our API
- **Documentation:** Link to OpenResponses docs for API reference

**Extensions needed:**
```yaml
# In agentic-responses-api/openresponses-spec-extensions.md
# (ALREADY DOCUMENTED, just implement)

# 1. function_call_approval_request / function_call_approval_response
# 2. oauth_login_request
# 3. user_interruption
# 4. response.output_item.updated (for ephemeral status)
# 5. response.nested.response.* (for sub-agent streams)
# 6. output_ui content type
```

**Development effort:** ~1-2 weeks to implement extensions and validate compliance

---

### 5. One Chat Conversation Storage (merged into MAS)

**What it provides:**
- ✅ Conversation CRUD operations
- ✅ Message storage
- ✅ Integration with estore
- ✅ Already merged into universe (commit 467d6bf)

**How we'll use it:**
- **Conversation persistence:** Use One Chat storage as-is
- **Auto-compaction:** Add compaction logic on top of storage layer

**Extensions needed:**
```python
# In kbqa/conversation/storage.py (or wherever One Chat storage lives)

class ConversationStorage:
    # EXISTING: create_conversation, get_conversation, add_message, etc.

    # NEW: Auto-compaction
    async def compact_conversation(
        self,
        conversation_id: str,
        strategy: CompactionStrategy,
    ) -> List[Message]:
        messages = await self.get_messages(conversation_id)

        if strategy.type == 'summarize':
            # Use LLM to summarize older messages
            summary = await self._summarize_messages(messages[:-10])
            # Keep last 10 messages + summary
            return [summary] + messages[-10:]

        elif strategy.type == 'truncate':
            # Keep last N messages
            return messages[-strategy.keep_recent:]

    # NEW: Conversation search/filter
    async def search_conversations(
        self,
        user_id: str,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> List[Conversation]:
        # Query conversations with filters
        ...
```

**Development effort:** ~1 week to add compaction and search

---

## Integration Architecture

Here's how all the pieces fit together:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER REQUEST                                  │
│  POST /mlflow/v1/responses                                       │
│  {                                                                │
│    "model": "sales_assistant",                                   │
│    "input": "Show me top customers",                             │
│    "conversation": "conv_123"                                    │
│  }                                                                │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                 MAS Request Handler                              │
│  (agentbricks/mas/python/server/handler.py)                     │
│  • Parse request                                                 │
│  • Authenticate user                                             │
│  • Load agent config from registry                              │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Agent Spec Parser                                │
│  (NEW: agentbricks/mas/python/agent/agent_spec.py)             │
│  • Parse agent.yaml                                              │
│  • Validate against schema                                       │
│  • Convert to aroll config + governance rules                   │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│             Aroll Supervisor                                     │
│  (agentbricks/mas/python/agent/supervisor_aroll.py)            │
│  • Load conversation history (from estore)                      │
│  • Initialize aroll environment                                 │
│  • Run agentic loop (think → act → observe)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Tool Orchestrator                                │
│  (research/aroll/aroll/tools/)                                  │
│  • Execute tools in parallel (when supported)                   │
│  • Handle tool approvals (NEW)                                  │
│  • Track cost/latency (NEW)                                     │
│                                                                  │
│  Tools:                                                          │
│  ├─ Genie (EXISTING in MAS)                                     │
│  ├─ UC Function (EXISTING in MAS)                               │
│  ├─ MCP Server (EXISTING in MAS)                                │
│  ├─ UC Table (NEW)                                              │
│  ├─ Code Interpreter (NEW)                                      │
│  └─ Web Search (NEW)                                            │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│             OpenResponses Event Emitter                          │
│  (NEW: agentbricks/mas/python/streaming/openresponses.py)      │
│  • Convert aroll events to OpenResponses format                 │
│  • Emit SSE events:                                             │
│    - response.created                                           │
│    - response.output_item.added/delta/done                     │
│    - function_call_approval_request (NEW)                      │
│    - response.done                                              │
└───────────────────────────┬─────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│            Conversation Storage (estore)                        │
│  (kbqa/conversation/storage.py)                                 │
│  • Save messages                                                 │
│  • Save tool calls & results                                    │
│  • Auto-compact on context overflow (NEW)                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│               Observability                                      │
│  • MLflow Traces (EXISTING in aroll)                            │
│  • UC Table Logging (NEW)                                       │
│  • Cost Tracking (NEW)                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                 RESPONSE TO USER                                 │
│  SSE stream:                                                     │
│  event: response.output_item.delta                              │
│  data: {"text": "Here are the top customers..."}                │
└─────────────────────────────────────────────────────────────────┘
```

## New Code to Write

Based on the reuse strategy, here's what needs to be **newly developed**:

### 1. Agent Spec Parser (~1-2 weeks)
**Location:** `agentbricks/mas/python/agent/agent_spec.py`

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
import yaml

@dataclass
class AgentSpec:
    name: str
    version: str
    description: str
    model: ModelConfig
    prompt: PromptConfig
    tools: List[ToolConfig]
    behavior: BehaviorConfig
    conversation: ConversationConfig
    tracing: TracingConfig
    governance: GovernanceConfig

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'AgentSpec':
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_aroll_config(self) -> Dict:
        """Convert agent spec to aroll config format"""
        return {
            'env': {
                'llm_endpoint_name': self.model.name,
                'temperature': self.model.temperature,
                'prompt': {
                    'system': {'prompt': self.prompt.system},
                },
                'tools': [tool.to_aroll_format() for tool in self.tools],
            },
            'output': {
                'mlflow': self.tracing.to_aroll_format() if self.tracing.enabled else None,
            },
        }
```

### 2. Tool Approval Manager (~2 weeks)
**Location:** `agentbricks/mas/python/agent/tool_approval.py`

```python
from enum import Enum
from typing import Dict, Optional

class ApprovalPolicy(Enum):
    ALWAYS_ALLOW = 'always_allow'
    ALWAYS_ASK = 'always_ask'
    SMART = 'smart'

class ToolApprovalManager:
    def __init__(self, policies: Dict[str, ApprovalPolicy]):
        self.policies = policies
        self.user_decisions = {}  # Store "always allow" decisions

    async def check_approval_required(
        self,
        tool_name: str,
        arguments: Dict,
        user_id: str,
    ) -> bool:
        """Check if tool call requires approval"""
        policy = self.policies.get(tool_name, ApprovalPolicy.ALWAYS_ASK)

        if policy == ApprovalPolicy.ALWAYS_ALLOW:
            return False

        # Check if user previously said "always allow"
        if (user_id, tool_name) in self.user_decisions:
            return False

        if policy == ApprovalPolicy.SMART:
            # Smart detection: check if tool is state-changing
            return self._is_state_changing(tool_name, arguments)

        return True

    def _is_state_changing(self, tool_name: str, arguments: Dict) -> bool:
        """Heuristic to detect state-changing operations"""
        # Check for write operations in function name
        write_verbs = ['create', 'update', 'delete', 'send', 'post', 'write', 'modify']
        return any(verb in tool_name.lower() for verb in write_verbs)

    async def record_decision(
        self,
        user_id: str,
        tool_name: str,
        decision: str,  # 'approve', 'always_approve', 'deny'
    ):
        """Record user's approval decision"""
        if decision == 'always_approve':
            self.user_decisions[(user_id, tool_name)] = True
```

### 3. OpenResponses Event Emitter (~2 weeks)
**Location:** `agentbricks/mas/python/streaming/openresponses.py`

```python
from typing import AsyncIterator, Dict, Any
import json

class OpenResponsesEmitter:
    def __init__(self, response_id: str):
        self.response_id = response_id
        self.output_index = 0

    async def emit_created(self) -> str:
        """Emit response.created event"""
        event = {
            'type': 'response.created',
            'response': {
                'id': self.response_id,
                'status': 'in_progress',
            },
        }
        return f"event: response.created\ndata: {json.dumps(event)}\n\n"

    async def emit_text_delta(self, text: str) -> str:
        """Emit response.output_item.delta event"""
        event = {
            'type': 'response.output_item.delta',
            'output_index': self.output_index,
            'delta': {
                'type': 'output_text_delta',
                'text': text,
            },
        }
        return f"event: response.output_item.delta\ndata: {json.dumps(event)}\n\n"

    async def emit_tool_approval_request(
        self,
        tool_name: str,
        arguments: Dict,
        reason: str,
    ) -> str:
        """Emit function_call_approval_request event"""
        event = {
            'type': 'function_call_approval_request',
            'id': f'approval_{self.response_id}_{self.output_index}',
            'call_id': f'call_{self.output_index}',
            'name': tool_name,
            'arguments': json.dumps(arguments),
            'reason': reason,
            'options': [
                {'value': 'approve', 'label': 'Allow this time'},
                {'value': 'always_approve', 'label': "Always allow (don't ask again)"},
                {'value': 'deny', 'label': 'Deny'},
            ],
        }
        return f"event: function_call_approval_request\ndata: {json.dumps(event)}\n\n"

    async def emit_done(self, output: List[Any]) -> str:
        """Emit response.done event"""
        event = {
            'type': 'response.done',
            'response': {
                'id': self.response_id,
                'status': 'completed',
                'output': output,
            },
        }
        return f"event: response.done\ndata: {json.dumps(event)}\n\n"
```

### 4. Governance Manager (~1-2 weeks)
**Location:** `agentbricks/mas/python/agent/governance.py`

```python
from datetime import datetime, timedelta
from typing import Dict, Optional

class GovernanceManager:
    def __init__(
        self,
        max_cost: Optional[float] = None,
        max_duration: Optional[int] = None,
        rate_limit: Optional[Dict] = None,
    ):
        self.max_cost = max_cost
        self.max_duration = max_duration
        self.rate_limit = rate_limit

        # Track usage
        self.current_cost = 0.0
        self.start_time = datetime.now()
        self.request_counts = {}  # user_id -> [(timestamp, count)]

    async def check_cost_limit(self, additional_cost: float):
        """Check if adding this cost would exceed limit"""
        if self.max_cost is None:
            return

        if self.current_cost + additional_cost > self.max_cost:
            raise GovernanceError(
                f"Cost limit exceeded: ${self.current_cost + additional_cost:.2f} > ${self.max_cost:.2f}"
            )

        self.current_cost += additional_cost

    async def check_duration_limit(self):
        """Check if execution has exceeded time limit"""
        if self.max_duration is None:
            return

        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed > self.max_duration:
            raise GovernanceError(
                f"Duration limit exceeded: {elapsed:.1f}s > {self.max_duration}s"
            )

    async def check_rate_limit(self, user_id: str):
        """Check if user has exceeded rate limit"""
        if self.rate_limit is None:
            return

        now = datetime.now()
        if user_id not in self.request_counts:
            self.request_counts[user_id] = []

        # Clean up old entries
        cutoff = now - timedelta(minutes=self.rate_limit.get('window_minutes', 1))
        self.request_counts[user_id] = [
            (ts, count) for ts, count in self.request_counts[user_id]
            if ts > cutoff
        ]

        # Check limit
        total = sum(count for ts, count in self.request_counts[user_id])
        if total >= self.rate_limit.get('requests_per_window', 60):
            raise GovernanceError(f"Rate limit exceeded for user {user_id}")

        # Record this request
        self.request_counts[user_id].append((now, 1))
```

### 5. UC Table Tool (~1 week)
**Location:** `research/aroll/aroll/tools/databricks_table.py`

```python
from databricks.sdk import WorkspaceClient
from typing import Dict, Any

class DatabricksTableTool:
    def __init__(
        self,
        table_name: str,
        workspace_client: WorkspaceClient,
        execute_as_user: bool = True,
    ):
        self.table_name = table_name
        self.ws = workspace_client
        self.execute_as_user = execute_as_user

    async def execute(self, query: str, user_context: Dict) -> str:
        """Execute SQL query on UC table"""
        # Build SQL statement
        sql = f"SELECT * FROM {self.table_name} WHERE {query}"

        # Execute with user's permissions (respects RLS, column masking)
        if self.execute_as_user:
            # Use on-behalf-of execution
            result = await self.ws.sql_statements.execute_on_behalf_of(
                user_id=user_context['user_id'],
                statement=sql,
            )
        else:
            # Execute as service principal
            result = await self.ws.sql_statements.execute(statement=sql)

        # Format result
        return self._format_result(result)

    def _format_result(self, result) -> str:
        """Format SQL result for LLM consumption"""
        # Convert to markdown table or JSON
        ...
```

### 6. Conversation Auto-Compaction (~1 week)
**Location:** `kbqa/conversation/compaction.py`

```python
from typing import List
from databricks.sdk import WorkspaceClient

class ConversationCompactor:
    def __init__(self, workspace_client: WorkspaceClient, summarization_model: str):
        self.ws = workspace_client
        self.summarization_model = summarization_model

    async def compact(
        self,
        messages: List[Message],
        strategy: str = 'summarize',
        keep_recent: int = 10,
    ) -> List[Message]:
        """Compact conversation history"""
        if len(messages) <= keep_recent:
            return messages

        if strategy == 'summarize':
            # Keep last N messages, summarize the rest
            old_messages = messages[:-keep_recent]
            recent_messages = messages[-keep_recent:]

            # Generate summary using LLM
            summary_prompt = self._build_summary_prompt(old_messages)
            summary_response = await self.ws.serving_endpoints.query(
                name=self.summarization_model,
                input=[{'role': 'user', 'content': summary_prompt}],
            )

            summary_message = Message(
                role='system',
                content=f"Previous conversation summary: {summary_response['output'][0]['text']}",
            )

            return [summary_message] + recent_messages

        elif strategy == 'truncate':
            # Simply keep last N messages
            return messages[-keep_recent:]

    def _build_summary_prompt(self, messages: List[Message]) -> str:
        """Build prompt for summarizing messages"""
        conversation_text = '\n'.join([
            f"{msg.role}: {msg.content}"
            for msg in messages
        ])

        return f"""Summarize the following conversation in 2-3 sentences. Focus on:
- What the user was trying to accomplish
- Key decisions or information shared
- Any unresolved issues

Conversation:
{conversation_text}

Summary:"""
```

### 7. Frontend Extensions (~2 weeks)
**Location:** `app-templates/e2e-chatbot-app-next/client/src/components/elements/`

```typescript
// ToolApprovalCard.tsx
export function ToolApprovalCard({
  toolName,
  arguments: args,
  reason,
  onApprove,
  onDeny,
}: {
  toolName: string;
  arguments: string;
  reason: string;
  onApprove: (decision: 'approve' | 'always_approve') => void;
  onDeny: () => void;
}) {
  return (
    <div className="border rounded-lg p-4 bg-yellow-50">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
        <div className="flex-1">
          <h4 className="font-semibold">Permission Required</h4>
          <p className="text-sm text-gray-600 mt-1">{reason}</p>

          <details className="mt-2">
            <summary className="text-sm cursor-pointer text-gray-500">
              View details
            </summary>
            <pre className="text-xs mt-2 bg-gray-100 p-2 rounded">
              {JSON.stringify(JSON.parse(arguments), null, 2)}
            </pre>
          </details>

          <div className="flex gap-2 mt-3">
            <button
              onClick={() => onApprove('approve')}
              className="btn btn-primary"
            >
              Allow this time
            </button>
            <button
              onClick={() => onApprove('always_approve')}
              className="btn btn-secondary"
            >
              Always allow
            </button>
            <button onClick={onDeny} className="btn btn-danger">
              Deny
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// OAuthLoginCard.tsx
export function OAuthLoginCard({
  provider,
  loginUrl,
  reason,
}: {
  provider: string;
  loginUrl: string;
  reason: string;
}) {
  return (
    <div className="border rounded-lg p-4 bg-blue-50">
      <div className="flex items-start gap-3">
        <Key className="w-5 h-5 text-blue-600 mt-0.5" />
        <div className="flex-1">
          <h4 className="font-semibold">Sign In Required</h4>
          <p className="text-sm text-gray-600 mt-1">{reason}</p>

          <a
            href={loginUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary mt-3"
          >
            Sign in to {provider}
          </a>
        </div>
      </div>
    </div>
  );
}

// CustomUIRenderer.tsx
export function CustomUIRenderer({ ui }: { ui: any }) {
  // Render custom UI based on type
  if (ui.type === 'chart') {
    return <ChartRenderer {...ui.props} />;
  } else if (ui.type === 'table') {
    return <DataTableRenderer {...ui.props} />;
  } else if (ui.type === 'map') {
    return <MapRenderer {...ui.props} />;
  }

  // Fallback: show raw JSON
  return <pre>{JSON.stringify(ui, null, 2)}</pre>;
}
```

## Development Effort Summary

| Component | Work Type | Effort | Priority |
|-----------|----------|--------|----------|
| **Agent Spec Parser** | New code | 1-2 weeks | P0 (Phase 0) |
| **Extend aroll config** | Modify existing | 2 weeks | P0 (Phase 0) |
| **Tool Approval Manager** | New code | 2 weeks | P0 (Phase 1) |
| **OpenResponses Emitter** | New code | 2 weeks | P0 (Phase 1) |
| **Governance Manager** | New code | 1-2 weeks | P1 (Phase 4) |
| **UC Table Tool** | New code | 1 week | P0 (Phase 1) |
| **Code Interpreter Tool** | New code | 2 weeks | P1 (Phase 5) |
| **Web Search Tool** | New code | 1 week | P1 (Phase 5) |
| **Conversation Compaction** | New code | 1 week | P1 (Phase 2) |
| **Frontend Extensions** | Modify existing | 2 weeks | P0 (Phase 1) |
| **Conversations API** | New code | 2 weeks | P1 (Phase 2) |
| **Background Mode** | New code | 3 weeks | P1 (Phase 5) |

**Total Phase 0-1 (MVP):** ~12-14 weeks (3-3.5 months)
**Total All Phases:** ~24 weeks (6 months)

## Key Reuse Wins

1. **aroll gives us 70% of runtime for free**
   - Async execution engine ✅
   - Multi-provider support ✅
   - Tool orchestration ✅
   - MLflow tracing ✅

2. **MAS gives us production-ready APIs**
   - HTTP handler ✅
   - Session management ✅
   - Tool registry (Genie, UC Function, MCP) ✅
   - Conversation storage integration ✅

3. **e2e-chatbot-app-next gives us UX**
   - React chat UI ✅
   - Vercel AI SDK streaming ✅
   - Databricks auth ✅
   - Feedback collection ✅
   - DAB deployment ✅

4. **OpenResponses gives us standards**
   - API schema ✅
   - Streaming events ✅
   - Multi-provider compatibility ✅
   - Compliance tests ✅

## Risk Mitigation

| Risk | Mitigation Strategy |
|------|-------------------|
| **aroll doesn't support X feature** | Fork aroll into our repo, extend as needed. Contribute back upstream. |
| **MAS's API format differs from OpenResponses** | Write translation layer in `OpenResponsesEmitter`. Keep MAS changes minimal. |
| **estore conversation storage insufficient** | Build separate Conversations API in Phase 2. Use estore as implementation detail. |
| **Vercel AI SDK doesn't support our extensions** | They already support OpenResponses. Our extensions are opt-in, degrade gracefully. |
| **Tool approvals slow down agent** | Cache approval decisions ("always allow"). Smart policy minimizes interruptions. |

## Next Steps

1. **Week 1:** Set up agent spec schema, extend aroll config parser
2. **Week 2:** Build basic API endpoint (`POST /mlflow/v1/responses`) without tools
3. **Week 3-4:** Implement UC Table tool + tool approval flow
4. **Week 5-6:** Add Genie, UC Function, MCP tools (reuse from MAS)
5. **Week 7-8:** Implement OpenResponses event emitter, validate streaming
6. **Week 9-10:** Extend chat UI with tool approvals, OAuth cards
7. **Week 11-12:** Conversation storage (CRUDL API), auto-compaction
8. **Week 13-14:** Governance (cost/time limits, rate limiting)
9. **Week 15-16:** Observability (traces to UC tables, dashboards)
10. **Week 17-20:** Advanced features (background mode, interrupts, long-term memory)
11. **Week 21-24:** SDK, adapters, visual builder

**Goal:** Ship MVP (Phase 0-1) in 3 months, full framework in 6 months.
