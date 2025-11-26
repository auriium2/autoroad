"""
HTTP client for calling worker services.
"""

import os
from collections.abc import AsyncIterator

import httpx

WORKER_URL = os.environ.get("WORKER_URL", "http://localhost:8080")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

# Timeout: None for streaming (we handle timeout via solver's max_time)
WORKER_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)


async def call_worker_optimize(request_data: dict[str, object]) -> AsyncIterator[str]:
    """
    Call the worker's /optimize endpoint and stream the SSE response.
    
    Yields raw SSE lines (including "data: " prefix).
    """
    headers = {"Accept": "text/event-stream"}
    if WORKER_SECRET:
        headers["Authorization"] = f"Bearer {WORKER_SECRET}"

    async with httpx.AsyncClient(timeout=WORKER_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{WORKER_URL}/optimize",
            json=request_data,
            headers=headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:  # Skip empty lines
                    yield line + "\n"
