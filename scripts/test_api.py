"""Test script for the /responses API."""
import requests
import json
import sys


def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    response = requests.get("http://localhost:8000/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


def test_non_streaming():
    """Test non-streaming response."""
    print("Testing non-streaming /responses...")
    payload = {
        "input": [{"role": "user", "content": "What is 2+2?"}],
        "stream": False,
        "databricks_options": {"user_id": 12345}
    }

    response = requests.post(
        "http://localhost:8000/responses",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


def test_streaming():
    """Test streaming response."""
    print("Testing streaming /responses...")
    payload = {
        "input": [{"role": "user", "content": "Count to 5"}],
        "stream": True,
        "databricks_options": {"user_id": 12345}
    }

    response = requests.post(
        "http://localhost:8000/responses",
        json=payload,
        headers={"Content-Type": "application/json"},
        stream=True
    )

    print(f"Status: {response.status_code}")
    print("Streaming events:")

    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                event_data = decoded_line[6:]  # Remove 'data: ' prefix
                if event_data != '[DONE]':
                    try:
                        event = json.loads(event_data)
                        print(f"  {event}")
                    except json.JSONDecodeError:
                        print(f"  {event_data}")
                else:
                    print(f"  {event_data}")

    print()
    return response.status_code == 200


def test_background():
    """Test background mode."""
    print("Testing background mode...")
    payload = {
        "input": [{"role": "user", "content": "Long running task"}],
        "background": True,
        "databricks_options": {"user_id": 12345}
    }

    response = requests.post(
        "http://localhost:8000/responses",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")

    if "id" in result:
        response_id = result["id"]
        print(f"\nRetrieving response {response_id}...")

        # Wait a moment for background task
        import time
        time.sleep(2)

        retrieve_response = requests.get(f"http://localhost:8000/responses/{response_id}")
        print(f"Status: {retrieve_response.status_code}")
        print(f"Response: {json.dumps(retrieve_response.json(), indent=2)}\n")

    return response.status_code == 200


def main():
    """Run all tests."""
    print("=" * 60)
    print("Agent Backend API Tests")
    print("=" * 60 + "\n")

    tests = [
        ("Health Check", test_health),
        ("Non-streaming Response", test_non_streaming),
        ("Streaming Response", test_streaming),
        ("Background Mode", test_background),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"ERROR in {name}: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {name}")

    all_passed = all(success for _, success in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
