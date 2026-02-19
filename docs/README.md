# Documentation Index

Complete documentation for building, deploying, and troubleshooting declarative agents with browser UI integration.

## 📖 Getting Started

**New to this project?** Start here:

1. **[Main README](../README.md)** - Project overview, quick start, API usage
2. **[Architecture Overview](ARCHITECTURE.md)** - Understanding the system design
3. **[UI Integration Guide](UI_INTEGRATION_GUIDE.md)** - Building your first agent with UI

## 🏗️ Architecture & Design

### [ARCHITECTURE.md](ARCHITECTURE.md)
**Complete system architecture reference**

Topics covered:
- End-to-end data flow from browser to LLM
- SSE streaming implementation details
- Authentication (local dev vs production)
- Event schema specifications
- Performance characteristics
- Security considerations

**When to read:** Understanding how components fit together, debugging integration issues, or designing new features.

## 🚀 Deployment & Integration

### [UI_INTEGRATION_GUIDE.md](UI_INTEGRATION_GUIDE.md)
**Step-by-step guide to building and deploying agents with web UI**

Topics covered:
- Part 1: Build the declarative agent (Python)
- Part 2: Deploy agent app to Databricks
- Part 3: Build the UI (React + Express)
- Part 4: Configure integration (SSE streaming)
- Part 5: Deploy the UI to Databricks Apps
- Testing procedures
- Troubleshooting guide

**When to read:** Building a new agent from scratch, integrating with a web UI, or deploying to production.

### [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)
**Deploying the agent backend**

Topics covered:
- Prerequisites and setup
- Local development configuration
- Databricks Apps deployment
- Database configuration (SQLite vs PostgreSQL)
- Environment variables

**When to read:** Deploying the backend without UI, or understanding backend-only deployment.

## 🐛 Debugging & Troubleshooting

### [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md)
**Complete debugging journey for SSE streaming issues**

Topics covered:
- Root causes of streaming failures
- Workspace mismatch issues
- Event schema validation errors
- Header conflicts
- Debugging methodology
- Testing checklist

**When to read:** Streaming not working, browser showing no text, validation errors, or authentication failures.

### [../STREAMING_FIX_SUMMARY.md](../STREAMING_FIX_SUMMARY.md)
**Legacy streaming fix documentation**

**Note:** This document covers the agent backend streaming implementation. For browser UI streaming issues, see [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md).

### [../PERMISSION_FIX.md](../PERMISSION_FIX.md)
**Databricks Apps permission configuration**

Topics covered:
- Service principal permissions
- CAN_USE vs CAN_MANAGE
- Granting app-to-app permissions
- Permission API usage

**When to read:** Getting 403 errors, HTML login pages, or "authentication failed" errors.

## 📊 Status & Progress

### [../DEPLOYMENT_STATUS.md](../DEPLOYMENT_STATUS.md)
**Current deployment state**

Contains:
- Test results (local and deployed)
- Known issues and limitations
- Validation results

**When to read:** Checking what's working, what's not, and what's tested.

### [../UI_DEPLOYMENT_STATUS.md](../UI_DEPLOYMENT_STATUS.md)
**UI app deployment details**

Contains:
- UI app URLs
- Deployment logs
- Integration status

**When to read:** Checking UI app deployment status and URLs.

## 🔧 SDK & Implementation

### [../sdk/README.md](../sdk/README.md)
**Declarative Agent SDK documentation**

Topics covered:
- YAML agent definitions
- Python API reference
- AgentRunner usage
- Streaming and background modes

**When to read:** Using the declarative agent SDK, defining agents via YAML.

### [../IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
**Complete implementation details**

Topics covered:
- Design decisions
- Database schema
- API implementation
- Testing strategy
- Code structure

**When to read:** Understanding implementation choices, contributing code, or extending functionality.

### [../FRAMEWORK_SPEC.md](../FRAMEWORK_SPEC.md)
**OpenResponses API specification**

Topics covered:
- OpenResponses format specification
- API endpoints and schemas
- SSE event types
- Tool orchestration

**When to read:** Implementing OpenResponses-compatible systems, understanding the spec, or building custom integrations.

## 📝 Examples

### [../examples/README.md](../examples/)
**Sample agents and usage patterns**

Contains:
- Example YAML agent definitions
- Python usage examples (streaming, non-streaming, background)
- Tool usage examples

**When to read:** Looking for code examples, learning by example, or getting started quickly.

## 🔍 Quick Reference

### Common Tasks

**Starting local development:**
```bash
# Backend
DB_TYPE=sqlite uvicorn server.main:app --reload

# UI (in separate terminal)
cd ~/app-templates/e2e-chatbot-app-next
npm run dev
```

**Testing:**
```bash
# Backend API tests
DB_TYPE=sqlite pytest tests/test_api_acceptance.py -v

# UI streaming test
cd ~/app-templates/e2e-chatbot-app-next
npx tsx tests/test_ui_streaming_debug.ts
```

**Deploying:**
```bash
# Backend
databricks bundle deploy -t dev

# UI
cd ~/app-templates/e2e-chatbot-app-next
npm run build
databricks bundle deploy -t dev
databricks bundle run databricks_chatbot -t dev
```

**Debugging streaming issues:**
1. Check [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md)
2. Verify workspace matches between UI and agent
3. Check browser console for validation errors
4. Test with curl to isolate client vs server issues

### Key URLs (Example)

- **Agent App:** https://dev-data-analyst-3217006663075879.aws.databricksapps.com
- **UI App:** https://db-chatbot-dev-sid-murching-3217006663075879.aws.databricksapps.com

## 🆘 Need Help?

**Issue checklist:**

1. **Not streaming in browser?** → [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md)
2. **Authentication errors?** → [PERMISSION_FIX.md](../PERMISSION_FIX.md) + [ARCHITECTURE.md](ARCHITECTURE.md) Authentication section
3. **Event validation errors?** → [STREAMING_DEBUG_GUIDE.md](STREAMING_DEBUG_GUIDE.md) Section 3
4. **Deployment failures?** → [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) + [DEPLOYMENT_STATUS.md](../DEPLOYMENT_STATUS.md)
5. **Agent not responding?** → [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) Testing section

## 📚 Document Relationships

```
Main README (Overview & Quick Start)
    │
    ├─→ docs/ARCHITECTURE.md (System Design)
    │
    ├─→ docs/UI_INTEGRATION_GUIDE.md (Full Tutorial)
    │   └─→ References ARCHITECTURE.md for technical details
    │
    ├─→ docs/STREAMING_DEBUG_GUIDE.md (Troubleshooting)
    │   └─→ References ARCHITECTURE.md for understanding
    │
    ├─→ DEPLOYMENT_GUIDE.md (Backend Deployment)
    │
    ├─→ IMPLEMENTATION_SUMMARY.md (Code Details)
    │
    └─→ sdk/README.md (SDK Reference)
```

## 🔄 Document Versions

- **Latest:** All docs updated as of 2026-02-18
- **Tested with:**
  - Databricks CLI 0.210.0+
  - Node.js 20.x
  - Python 3.10+
  - Vercel AI SDK (latest)

---

**Happy building! 🚀**

For questions or issues, refer to the appropriate documentation section above or check the troubleshooting guides.
