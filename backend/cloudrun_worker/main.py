"""
Cloud Run worker for optimization requests.

Optimized for fast cold starts - uses minimal imports at startup.
Heavy dependencies (ortools, polars, pydantic) loaded lazily on first request.
"""

import json
import os
import sys

sys.path.insert(0, "/app")
os.environ["CPSAT_NUM_WORKERS"] = "8"

_app = None
_models = None
_optimize = None


def get_app():
    global _app
    if _app is None:
        from fastapi import FastAPI, Request
        from fastapi.responses import StreamingResponse

        _app = FastAPI()

        @_app.get("/health")
        async def health():
            return {"status": "healthy", "service": "cloudrun-worker", "cpus": 8}

        @_app.post("/optimize")
        async def optimize(request: Request):
            OptimizationRequest = get_models().OptimizationRequest
            run_optimization = get_optimize().run_optimization

            data = await request.json()
            opt_request = OptimizationRequest(**data)

            async def event_stream():
                try:
                    async for event in run_optimization(opt_request):
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
            )

    return _app


def get_models():
    global _models
    if _models is None:
        from shared.models import requests
        _models = requests
    return _models


def get_optimize():
    global _optimize
    if _optimize is None:
        from shared import optimize
        _optimize = optimize
    return _optimize


def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"[WORKER] Starting on port {port}")
    uvicorn.run(get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
