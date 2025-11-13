#!/bin/bash
# Start arq worker for optimization jobs
#
# Usage:
#   ./start_worker.sh                    # Start 1 worker
#   ./start_worker.sh --max-jobs 8       # Start worker with 8 concurrent jobs
#
# Scale horizontally:
#   Run this script on multiple machines/containers pointing to same Redis

cd /Users/matt/summer/autoroad

# Default configuration
MAX_JOBS=${MAX_JOBS:-4}
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

echo "Starting arq worker..."
echo "  Redis: $REDIS_HOST:$REDIS_PORT"
echo "  Max concurrent jobs: $MAX_JOBS"

# Run arq worker
uv run arq backend.api.workers.main.WorkerSettings
