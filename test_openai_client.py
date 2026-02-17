"""Quick test to verify OpenAI client compatibility."""
import asyncio
from openai import AsyncOpenAI


async def test_responses_create():
    """Test that client.responses.create works with our server."""
    client = AsyncOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="",  # Empty for local testing
    )

    try:
        # This should work if our server is OpenAI-compatible
        response = await client.responses.create(
            model="databricks-gpt-5-2",
            input="Hello, how are you?",
        )

        print(f"✓ Response created: {response.id}")
        print(f"  Output: {response.output}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    result = asyncio.run(test_responses_create())
    exit(0 if result else 1)
