FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (production only)
RUN uv sync --frozen --no-dev

# Copy application code
COPY shared/ ./shared/
COPY worker/ ./worker/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CPSAT_NUM_WORKERS=4

# Run worker as HTTP server (Cloud Run expects port 8080)
CMD ["uv", "run", "uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8080"]
