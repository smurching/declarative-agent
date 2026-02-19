"""
Test the UI app integration with the agent app.

This tests the full stack: UI → Agent App → Backend → LLM
"""
import pytest
import httpx
from databricks.sdk import WorkspaceClient
import uuid


@pytest.fixture
def ui_app_url():
    """UI app URL."""
    return "https://db-chatbot-dev-sid-murching-3217006663075879.aws.databricksapps.com"


@pytest.fixture
def auth_token():
    """Get authentication token."""
    w = WorkspaceClient()
    return w.config.oauth_token().access_token


@pytest.mark.asyncio
async def test_ui_app_health(ui_app_url, auth_token):
    """Test UI app is accessible."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            ui_app_url,
            headers={"Authorization": f"Bearer {auth_token}"},
            follow_redirects=True
        )
        assert response.status_code == 200, f"UI app not accessible: {response.status_code}"


@pytest.mark.asyncio
async def test_ui_to_agent_integration(ui_app_url, auth_token):
    """Test full stack: UI → Agent App → Backend → LLM."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Send a chat message via UI app API
        chat_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())

        response = await client.post(
            f"{ui_app_url}/api/chat",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "id": chat_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "What is 2+2?"}],
                    "id": msg_id
                },
                "selectedChatModel": "chat-model",
                "selectedVisibilityType": "private"
            }
        )

        # UI returns streaming response
        assert response.status_code == 200, f"Chat API failed: {response.status_code} - {response.text}"

        # Collect the response
        chunks = []
        async for line in response.aiter_lines():
            if line:
                chunks.append(line)

        response_text = "\n".join(chunks)

        # Verify we got a response
        assert len(response_text) > 0, "Should receive response from agent"

        # Verify it contains answer to 2+2
        assert "4" in response_text.lower(), f"Response should contain '4': {response_text}"


if __name__ == "__main__":
    import asyncio

    # Quick manual test
    async def main():
        w = WorkspaceClient()
        token = w.config.oauth_token().access_token
        ui_url = "https://db-chatbot-dev-sid-murching-3217006663075879.aws.databricksapps.com"

        print(f"Testing UI app at: {ui_url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            print("\n1. Testing UI app health...")
            health_resp = await client.get(
                ui_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True
            )
            print(f"   Status: {health_resp.status_code}")

            print("\n2. Testing chat API...")
            chat_id = str(uuid.uuid4())
            msg_id = str(uuid.uuid4())

            chat_resp = await client.post(
                f"{ui_url}/api/chat",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "id": chat_id,
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "What is 2+2?"}],
                        "id": msg_id
                    },
                    "selectedChatModel": "chat-model",
                    "selectedVisibilityType": "private"
                }
            )
            print(f"   Status: {chat_resp.status_code}")

            if chat_resp.status_code == 200:
                print("\n3. Response preview:")
                count = 0
                async for line in chat_resp.aiter_lines():
                    if line and count < 10:
                        print(f"   {line[:100]}")
                        count += 1
                        if count >= 10:
                            print("   ...")
                            break
            else:
                print(f"   Error: {chat_resp.text}")

    asyncio.run(main())
