import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

from server.routes import bug_report, courses, optimize, requirements

limiter = Limiter(key_func=get_remote_address)

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")

app = FastAPI(
    title="Autoroad API",
    description="Course planning and optimization for MIT students",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize.router, prefix="/api", tags=["optimization"])
app.include_router(requirements.router, prefix="/api", tags=["requirements"])
app.include_router(courses.router, prefix="/api", tags=["courses"])
app.include_router(bug_report.router, prefix="/api", tags=["bug-report"])


@app.get("/api/health")
async def health():
    import httpx

    services: dict[str, dict[str, str]] = {
        "backend": {"status": "healthy"},
        "fireroad": {"status": "unknown"},
    }
    status = "healthy"

    # Check Fireroad API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://fireroad.mit.edu/courses/lookup/6.100A")
            if resp.status_code == 200:
                services["fireroad"] = {"status": "healthy"}
            else:
                services["fireroad"] = {"status": "unhealthy", "error": f"HTTP {resp.status_code}"}
                status = "degraded"
    except Exception as e:
        services["fireroad"] = {"status": "unhealthy", "error": str(e)}
        status = "degraded"

    return {"status": status, "services": services}
