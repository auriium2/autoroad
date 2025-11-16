"""
Test the optimization API endpoint.
"""

import requests
import json

API_URL = "http://localhost:8000"


def test_optimize_endpoint():
    """Test the /api/optimize endpoint with a simple request."""
    
    # Prepare request
    request_body = {
        "markers": [
            {
                "courseId": "6.100A",
                "section": 0,
                "status": "pin"
            }
        ],
        "requirements": ["girs"],
        "constraints": {
            "maxSemesters": 12,
            "maxUnitsPerSemester": 60,
            "maxUnitsIAP": 12,
            "maxHoursPerSemester": 60
        }
    }
    
    print("Sending optimization request...")
    print(f"Request: {json.dumps(request_body, indent=2)}")
    
    # Make request with streaming
    response = requests.post(
        f"{API_URL}/api/optimize",
        json=request_body,
        stream=True,
        headers={"Accept": "text/event-stream"}
    )
    
    if response.status_code != 200:
        print(f"✗ Request failed with status {response.status_code}")
        print(response.text)
        return
    
    print("\n" + "="*60)
    print("Streaming results:")
    print("="*60)
    
    # Parse SSE stream
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix
                try:
                    message = json.loads(data)
                    
                    if message.get('type') == 'progress':
                        print(f"[Progress {message.get('step')}/{message.get('totalSteps')}] {message.get('message')}")
                    
                    elif message.get('type') == 'solution':
                        print(f"\n[Solution {message.get('step')}] Found {len(message.get('nodes', []))} courses")
                        print(f"  Objective value: {message.get('objectiveValue')}")
                        
                        # Print first few courses
                        for node in message.get('nodes', [])[:5]:
                            print(f"    - {node.get('courseId')} (semester {node.get('section')})")
                        
                        if len(message.get('nodes', [])) > 5:
                            print(f"    ... and {len(message.get('nodes', [])) - 5} more courses")
                    
                    elif message.get('type') == 'complete':
                        print(f"\n✓ Optimization complete!")
                        print(f"  Status: {message.get('status')}")
                        print(f"  Solutions found: {message.get('solutionCount')}")
                        
                        if message.get('warnings'):
                            print(f"  Warnings:")
                            for warning in message.get('warnings', []):
                                print(f"    - {warning}")
                        
                        return
                    
                    elif message.get('type') == 'error':
                        print(f"\n✗ Error: {message.get('error')}")
                        print(f"  Details: {message.get('details')}")
                        return
                
                except json.JSONDecodeError as e:
                    print(f"Failed to parse: {data}")


if __name__ == "__main__":
    print("Testing Autoroad API")
    print("Make sure the server is running: uv run uvicorn api.main:app --port 8000")
    print()
    
    # Test health endpoint
    try:
        health = requests.get(f"{API_URL}/health")
        if health.status_code == 200:
            print("✓ Server is healthy")
        else:
            print(f"✗ Health check failed: {health.status_code}")
            exit(1)
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        exit(1)
    
    print()
    test_optimize_endpoint()
