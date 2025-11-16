import asyncio
import json

async def test_stream():
    """Test if SSE streaming works"""
    async def event_stream():
        for i in range(5):
            yield f"data: {json.dumps({'step': i, 'message': f'Step {i}'})}\n\n"
            await asyncio.sleep(0.5)  # Simulate work
    
    async for event in event_stream():
        print(event, end='', flush=True)

if __name__ == "__main__":
    asyncio.run(test_stream())
