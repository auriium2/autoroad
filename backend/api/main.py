from contextlib import asynccontextmanager

from backend.api.routes import optimize
from backend.api.services.redis_client import close_redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Autoroad API server...")
    yield
    print("Shutting down Autoroad API server...")
    await close_redis()


app = FastAPI(
    title="Autoroad API",
    description="Course planning and optimization API for MIT students",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize.router, prefix="/api", tags=["optimization"])


@app.get("/")
async def root():
    return {
        "message": "Autoroad API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
