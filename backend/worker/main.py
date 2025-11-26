"""
Worker service that handles optimization requests via HTTP.

Deployed to Cloud Run, receives POST requests from the server,
runs optimization, and streams results back via SSE.
"""

import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from shared import OptimizationRequest, event_stream

app = FastAPI(title="AutoRoad Worker")

WORKER_SECRET = os.environ.get("WORKER_SECRET", "")


def verify_auth(authorization: str | None = Header(None)):
    if not WORKER_SECRET:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer" or parts[1] != WORKER_SECRET:
        raise HTTPException(status_code=401, detail="Invalid authorization")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "worker"}


@app.post("/optimize")
async def optimize(request: OptimizationRequest, authorization: str | None = Header(None)):
    verify_auth(authorization)
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )
