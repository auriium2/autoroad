from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routes import optimize, courses, requirements


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Autoroad API server...")
    yield
    print("Shutting down Autoroad API server...")


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
app.include_router(courses.router, prefix="/api", tags=["courses"])
app.include_router(requirements.router, prefix="/api", tags=["requirements"])


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
