FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# genuinely cursed import hackery for google cloud run cold start optimization
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && \
    # Remove unused ortools modules - only need sat (~8MB savings)
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/constraint_solver && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/math_opt && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/linear_solver && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/graph && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/set_cover && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/pdlp && \
    rm -rf /app/.venv/lib/python3.12/site-packages/ortools/scheduling && \
    # Remove unused numpy modules (~3MB savings - keep random for pandas)
    rm -rf /app/.venv/lib/python3.12/site-packages/numpy/f2py && \
    rm -rf /app/.venv/lib/python3.12/site-packages/numpy/polynomial && \
    rm -rf /app/.venv/lib/python3.12/site-packages/numpy/fft && \
    # Remove test files (~18MB savings)
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    # Precompile all Python files for faster cold starts
    python -m compileall -q /app/.venv/lib/python3.12/site-packages/

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY shared/ ./shared/
COPY cloudrun_worker/ ./cloudrun_worker/
COPY requirements/ ./requirements/

ENV PYTHONUNBUFFERED=1
ENV CPSAT_NUM_WORKERS=8
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["python", "-m", "cloudrun_worker.main"]
