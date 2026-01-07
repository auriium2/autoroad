import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from server.routes import courses, optimize, requirements

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")

app = FastAPI(
    title="Autoroad API",
    description="Course planning and optimization for MIT students",
    version="1.0.0",
)
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


@app.get("/api/health")
async def health():
    import httpx

    result = {
        "status": "healthy",
        "services": {
            "backend": {"status": "healthy"},
            "fireroad": {"status": "unknown"},
        }
    }

    # Check Fireroad API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://fireroad.mit.edu/courses/lookup/6.100A")
            if resp.status_code == 200:
                result["services"]["fireroad"] = {"status": "healthy"}
            else:
                result["services"]["fireroad"] = {"status": "unhealthy", "error": f"HTTP {resp.status_code}"}
                result["status"] = "degraded"
    except Exception as e:
        result["services"]["fireroad"] = {"status": "unhealthy", "error": str(e)}
        result["status"] = "degraded"

    return result
