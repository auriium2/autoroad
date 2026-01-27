import logging
import os

logger = logging.getLogger("uvicorn.error")
logging.getLogger("httpx").handlers = logger.handlers
logging.getLogger("httpx").setLevel(logging.INFO)

try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment from .env file")
except ImportError:
    logger.info("python-dotenv not installed, using environment variables directly")

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=0.1,
        environment=os.environ.get("ENVIRONMENT", "development"),
    )

from server.routes import bug_report, courses, hydrant, optimize, requirements

limiter = Limiter(key_func=get_remote_address)

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")

app = FastAPI(
    title="Autoroad API",
    description="Course planning and optimization for MIT students",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

app.include_router(optimize.router, prefix="/api", tags=["optimization"])
app.include_router(requirements.router, prefix="/api", tags=["requirements"])
app.include_router(courses.router, prefix="/api", tags=["courses"])
app.include_router(hydrant.router, prefix="/api", tags=["hydrant"])
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
