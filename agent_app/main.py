"""
Databricks App hosting a declarative agent.

This app loads a declarative agent YAML and exposes a chat endpoint.
It uses the AgentRunner SDK to call the backend /responses API.
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import os
import sys
import logging
import json

# Import from installed package
try:
    # When installed as package
    from declarative_agent import DeclarativeAgent, AgentRunner
except ImportError:
    # When running from source
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from sdk.declarative_agent import DeclarativeAgent, AgentRunner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Data Analyst Agent",
    description="Declarative agent for data analysis with SQL and Python",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load agent configuration
# Support both environment variable (for CLI) and default path (for direct deployment)
default_agent_path = Path(__file__).parent / "examples" / "agents" / "data_analyst.yaml"
AGENT_PATH = Path(os.getenv("AGENT_YAML_PATH", str(default_agent_path)))
BACKEND_URL = os.getenv("BACKEND_APP_URL", "http://localhost:8000")
ALLOWED_API_KEY = os.getenv("ALLOWED_API_KEY")  # Optional API key for app-to-app auth

logger.info(f"Loading agent from: {AGENT_PATH}")
logger.info(f"Backend URL: {BACKEND_URL}")
if ALLOWED_API_KEY:
    logger.info("API key authentication enabled")


async def verify_api_key(authorization: Optional[str] = Header(None)):
    """
    Verify API key from Authorization header.
    If ALLOWED_API_KEY is set, require it. Otherwise, allow all requests.
    """
    if not ALLOWED_API_KEY:
        # No API key configured - allow all requests (fallback to Databricks auth)
        return True

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )

    token = parts[1]
    if token != ALLOWED_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    return True

# Load the declarative agent
try:
    agent = DeclarativeAgent.from_yaml(AGENT_PATH, backend_url=BACKEND_URL)
    logger.info(f"✓ Loaded agent: {agent.config.name}")
except Exception as e:
    logger.error(f"Failed to load agent: {e}")
    raise


class InvocationsRequest(BaseModel):
    """
    OpenResponses-compatible request for /invocations endpoint.

    Expected format from chat UIs like e2e-chatbot-app-next.
    """
    input: List[Dict[str, str]]  # Messages: [{"role": "user", "content": "..."}]
    stream: bool = False
    background: bool = False
    databricks_options: Optional[Dict[str, Any]] = None  # Contains user_id, conversation_id


class InvocationsResponse(BaseModel):
    """
    OpenResponses-compatible response for /invocations endpoint.

    Returned for non-streaming and background modes.
    """
    id: str
    status: Optional[str] = None
    output: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None


@app.get("/")
async def root():
    """Root endpoint - agent info."""
    return {
        "agent": agent.config.name,
        "description": agent.config.description,
        "backend_url": BACKEND_URL,
        "capabilities": {
            "streaming": True,
            "background": True,
            "tools": len(agent.config.tools) if hasattr(agent.config, 'tools') else 0
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": agent.config.name,
        "backend_url": BACKEND_URL
    }


@app.post("/invocations")
async def invocations(
    request: InvocationsRequest,
    authorized: bool = Depends(verify_api_key)
):
    """
    OpenResponses-compatible /invocations endpoint.

    Consumed by chat UIs like e2e-chatbot-app-next.
    Forwards requests to backend /v1/responses via AgentRunner.

    Supports:
    - Streaming mode (returns SSE stream)
    - Non-streaming mode (returns JSON response)
    - Background mode (returns task ID immediately)
    - Multi-turn conversations (via conversation_id)
    """
    try:
        # Extract databricks_options
        databricks_options = request.databricks_options or {}
        user_id = databricks_options.get("user_id", 1000)
        conversation_id = databricks_options.get("conversation_id")

        # Extract last user message from input
        if not request.input:
            raise HTTPException(status_code=400, detail="input must contain at least one message")

        user_message = request.input[-1].get("content", "")
        if not user_message:
            raise HTTPException(status_code=400, detail="User message content cannot be empty")

        async with AgentRunner(agent, user_id=user_id) as runner:
            if request.background:
                # Background mode - returns immediately with task ID
                response = await runner.run(
                    message=user_message,
                    background=True,
                    conversation_id=conversation_id
                )
                return InvocationsResponse(
                    id=response["id"],
                    status=response["status"],
                    conversation_id=response.get("conversation_id")
                )

            elif request.stream:
                # Streaming mode - returns SSE stream
                async def stream_events():
                    """Stream SSE events from backend to client."""
                    try:
                        async for event in runner.run_streaming(
                            message=user_message,
                            conversation_id=conversation_id
                        ):
                            # Format as SSE: data: {...}\n\n
                            yield f"data: {json.dumps(event)}\n\n"
                        # Send [DONE] signal
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.exception(f"Error in streaming: {e}")
                        error_event = {
                            "type": "error",
                            "error": {"message": str(e), "type": "server_error"}
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"

                return StreamingResponse(
                    stream_events(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable nginx buffering
                    }
                )

            else:
                # Non-streaming mode - returns complete JSON response
                response = await runner.run(
                    message=user_message,
                    stream=False,
                    conversation_id=conversation_id
                )
                return InvocationsResponse(
                    id=response["id"],
                    output=response["output"],
                    conversation_id=response.get("conversation_id")
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in /invocations endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
async def get_task(task_id: str, user_id: int = 1000):
    """
    Retrieve a background task result.

    Args:
        task_id: Task ID returned from background request
        user_id: User ID (for authentication)
    """
    try:
        async with AgentRunner(agent, user_id=user_id) as runner:
            result = await runner.retrieve(task_id)
            return InvocationsResponse(
                id=result["id"],
                status=result["status"],
                output=result.get("output")
            )
    except Exception as e:
        logger.exception(f"Error retrieving task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation details (proxied from backend)."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BACKEND_URL}/conversations/{conversation_id}"
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.exception(f"Error fetching conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
