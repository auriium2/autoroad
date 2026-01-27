import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import httpx

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
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
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

if os.environ.get("FASTAPI_SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["FASTAPI_SENTRY_DSN"],
        environment=os.environ.get("FASTAPI_ENVIRONMENT", "development"),
        release=os.environ.get("FASTAPI_RELEASE_VERSION"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        # Attach request data (IPs, headers, bodies) - disable in prod if PII is a concern
        send_default_pii=True,
        # Attach all log levels as breadcrumbs, send ERROR+ as events
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            HttpxIntegration(),  # Auto-instrument httpx calls to Fireroad/Hydrant
            LoggingIntegration(
                level=logging.DEBUG,  # Capture DEBUG+ as breadcrumbs
                event_level=None,  # Don't send log messages as events, only use for breadcrumbs
            ),
        ],
        # Filter out health check noise
        traces_sampler=lambda ctx: 0 if ctx.get("asgi_scope", {}).get("path") == "/api/health" else 1.0,
    )

from server.routes import bug_report, courses, hydrant, optimize, requirements
from shared.services.cache import close_http_client, get_http_client

limiter = Limiter(key_func=get_remote_address)

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage app lifecycle - initialize and cleanup shared resources."""
    # Startup: initialize shared HTTP client
    get_http_client()
    logger.info("Initialized shared HTTP client for connection pooling")
    yield
    # Shutdown: close shared HTTP client
    await close_http_client()
    logger.info("Closed shared HTTP client")


is_production = os.environ.get("FASTAPI_ENVIRONMENT") == "production"

app = FastAPI(
    title="Autoroad API",
    description="Course planning and optimization for MIT students",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
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


def _get_allowed_sentry_host() -> str | None:
    dsn = os.environ.get("FASTAPI_SENTRY_DSN")
    if not dsn:
        return None
    parsed = urlparse(dsn)
    return parsed.hostname


ALLOWED_SENTRY_HOST = _get_allowed_sentry_host()


@app.post("/api/sentry-tunnel")
async def sentry_tunnel(request: Request):
    body = await request.body()
    lines = body.split(b"\n")
    if not lines:
        return Response(status_code=400)

    # Parse envelope header to get DSN
    try:
        header = json.loads(lines[0])
        dsn = header.get("dsn")
        if not dsn:
            return Response(status_code=400)

        # Extract project ID from DSN
        # DSN format: https://key@org.ingest.sentry.io/project_id
        parsed = urlparse(dsn)

        # anti ssrf patch
        if not ALLOWED_SENTRY_HOST or parsed.hostname != ALLOWED_SENTRY_HOST:
            return Response(status_code=400)

        project_id = parsed.path.strip("/")
        sentry_host = f"https://{parsed.hostname}"

        # Forward to Sentry
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{sentry_host}/api/{project_id}/envelope/",
                content=body,
                headers={"Content-Type": "application/x-sentry-envelope"},
            )
            return Response(status_code=response.status_code)
    except Exception:
        return Response(status_code=500)


@app.get("/api/health")
async def health():
    services: dict[str, dict[str, str]] = {
        "backend": {"status": "healthy"},
        "fireroad": {"status": "unknown"},
    }
    status = "healthy"

    # Check Fireroad API using shared client
    try:
        client = get_http_client()
        resp = await client.get("https://fireroad.mit.edu/courses/lookup/6.100A", timeout=5.0)
        if resp.status_code == 200:
            services["fireroad"] = {"status": "healthy"}
        else:
            services["fireroad"] = {"status": "unhealthy", "error": f"HTTP {resp.status_code}"}
            status = "degraded"
    except Exception as e:
        services["fireroad"] = {"status": "unhealthy", "error": str(e)}
        status = "degraded"

    return {"status": status, "services": services}
