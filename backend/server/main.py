import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from server.routes import courses, optimize, requirements

USE_WORKERS = os.environ.get("USE_WORKERS", "true").lower() == "true"
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


@app.get("/")
async def root():
    return {
        "message": "Autoroad API",
        "version": "1.0.0",
        "docs": "/docs",
        "mode": "workers" if USE_WORKERS else "local"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "mode": "workers" if USE_WORKERS else "local"}
