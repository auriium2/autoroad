# Autoroad FastAPI Backend

Scalable course planning optimization API with Redis-backed job queue and SSE streaming.

## Architecture

```
┌──────────┐                ┌─────────────┐
│  Client  │───POST────────►│ FastAPI API │
└──────────┘                └──────┬──────┘
     │                             │
     │                             ▼
     │                        ┌─────────┐
     │                        │  Redis  │
     │                        └────┬────┘
     │                             │
     │ SSE Stream                  │ Job Queue
     │ (Redis Stream)              │
     │                             ▼
     │                    ┌─────────────────┐
     └────────────────────┤  arq Worker 1   │
                          └─────────────────┘
                          ┌─────────────────┐
                          │  arq Worker 2   │
                          └─────────────────┘
                          ┌─────────────────┐
                          │  arq Worker N   │
                          └─────────────────┘
```

---

## Setup

```bash
# Install dependencies with uv
uv pip install fastapi uvicorn ortools pandas requests pydantic cachetools

# Run the server
cd /Users/matt/summer/autoroad
uv run uvicorn backend.api.main:app --reload --port 8000
```

### 3. Start Worker(s)
```bash
# Terminal 1: Start first worker
./backend/api/start_worker.sh

# Terminal 2: Start second worker (optional - for scaling)
./backend/api/start_worker.sh

To manually clear cache: `POST /api/optimize/clear-cache`

**Worker Configuration:**
- Each worker handles up to 4 concurrent jobs by default
- Modify `max_jobs` in `backend/api/workers/main.py` to change concurrency
- Workers can run on different machines pointing to same Redis

### Health Check
```
GET /health
```

**Different machines:**
```bash
# Machine 1
export REDIS_HOST=your-redis-server.com
./backend/api/start_worker.sh

# Machine 2
export REDIS_HOST=your-redis-server.com
./backend/api/start_worker.sh
```

**Docker/Kubernetes:**
```yaml
# docker-compose.yml
services:
  worker:
    build: .
    command: arq backend.api.workers.main.WorkerSettings
    environment:
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 5  # Run 5 workers
```

---

## API Endpoints

### Optimization

#### Start Optimization (with SSE streaming)
```http
POST /api/optimize
Content-Type: application/json

{
  "markers": [
    {
      "courseId": "6.1200",
      "section": 1,
      "status": "pin"
    }
  ],
  "requirements": ["major6-3new", "girs"],
  "constraints": {
    "maxSemesters": 12,
    "maxUnitsPerSemester": 60,
    "maxUnitsIAP": 12
  }
}
```

**Returns:** SSE stream with real-time progress

**Event Types:**
- `progress`: Status updates (e.g., "Building model...")
- `solution`: New solution found
- `complete`: Optimization finished
- `error`: Error occurred

#### Get Optimization Result
```http
GET /api/optimize/{job_id}
```

Retrieve the result of a completed optimization job. Useful if:
- SSE stream was interrupted
- Client disconnected and wants to retrieve results
- Polling for job completion

**Response codes:**
- `200`: Job completed, returns full result with solution nodes
- `202`: Job still running/queued
- `404`: Job not found or expired (results expire after 1 hour)

**Example response:**
```json
{
  "status": "completed",
  "result": {
    "status": "OPTIMAL",
    "solutionCount": 15,
    "nodes": [
      {"courseId": "6.1200", "semester": 1, "title": "Software Construction"}
    ],
    "warnings": []
  }
}
```

#### Cancel Optimization
```http
DELETE /api/optimize/{job_id}
```

Cancels a queued or running optimization job. Uses two-phase cancellation:
1. Aborts job if still in queue (immediate)
2. Signals running job to stop at next solution (~1-2 seconds)

#### Clear Cache
```http
POST /api/optimize/clear-cache
```

### Health Check
```http
GET /health
```

---

## SSE Event Examples

### Progress Event
```json
{
  "type": "progress",
  "message": "Starting solver...",
  "step": 5
}
```

### Solution Event
```json
{
  "type": "solution",
  "step": 1,
  "nodes": [
    {
      "courseId": "6.1200",
      "semester": 1,
      "title": "Software Construction"
    }
  ],
  "semesterUnits": [12, 0, 0, 48, 0, 0, 60, 0, 0, 48, 0, 0],
  "groupVars": {
    "GIRs": true,
    "Fundamentals": true
  }
}
```

### Complete Event
```json
{
  "type": "complete",
  "status": "OPTIMAL",
  "solutionCount": 15,
  "warnings": []
}
```

---

## Frontend Integration

### Option 1: SSE Streaming (Recommended)

```typescript
const response = await fetch('http://localhost:8000/api/optimize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    markers: [],
    requirements: ['major6-3new', 'girs']
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

let jobId: string | null = null;

// Cancel function for user to call
const cancelOptimization = async () => {
  if (jobId) {
    await fetch(`http://localhost:8000/api/optimize/${jobId}`, {
      method: 'DELETE'
    });
  }
};

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      
      switch (data.type) {
        case 'job_started':
          jobId = data.job_id;
          console.log(`Job started: ${jobId}`);
          // Show cancel button to user
          break;
          
        case 'progress':
          console.log(`Step ${data.step}: ${data.message}`);
          break;
          
        case 'solution':
          updateUI(data.nodes);
          break;
          
        case 'complete':
          console.log(`Done! Status: ${data.status}`);
          break;
          
        case 'error':
          console.error(data.error);
          break;
      }
    }
  }
}
```

### Option 2: Polling (Fallback/Simple)

```typescript
// Start optimization
const startResponse = await fetch('http://localhost:8000/api/optimize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    markers: [],
    requirements: ['major6-3new', 'girs']
  })
});

// Extract job_id from first SSE message
const reader = startResponse.body.getReader();
const decoder = new TextDecoder();
const { value } = await reader.read();
const firstMessage = JSON.parse(decoder.decode(value).split('data: ')[1]);
const jobId = firstMessage.job_id;

// Close stream and poll instead
reader.cancel();

// Poll for result
const pollResult = async () => {
  while (true) {
    const response = await fetch(`http://localhost:8000/api/optimize/${jobId}`);
    const data = await response.json();
    
    if (data.status === 'completed') {
      console.log('Optimization complete!');
      console.log('Solution:', data.result.nodes);
      return data.result;
    } else if (data.status === 'running' || data.status === 'queued') {
      console.log('Still running...');
      await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2s
    } else {
      throw new Error('Job failed or not found');
    }
  }
};

const result = await pollResult();
```

### Option 3: Hybrid (SSE with Recovery)

```typescript
let jobId: string | null = null;

const startOptimization = async () => {
  try {
    // Try SSE first
    const response = await fetch('http://localhost:8000/api/optimize', {
      method: 'POST',
      body: JSON.stringify(request)
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      // Handle messages...
      
      const data = JSON.parse(chunk.split('data: ')[1]);
      if (data.type === 'job_started') {
        jobId = data.job_id;
      }
    }
  } catch (error) {
    console.error('SSE stream failed:', error);
    
    // Fallback: poll for result if we have job_id
    if (jobId) {
      console.log('Falling back to polling...');
      const result = await fetch(`http://localhost:8000/api/optimize/${jobId}`);
      return await result.json();
    }
  }
};
```

---

## Caching

The API caches Fireroad data with TTL:
- **Course data**: 1 hour TTL (auto-eviction)
- **Requirements**: 1 hour TTL per requirement key
- **Thread-safe**: Uses `threading.RLock`

Manual cache clear: `POST /api/optimize/clear-cache`

---

## Monitoring

### Check Redis
```bash
# Connect to Redis CLI
redis-cli

# Check active jobs
KEYS arq:job:*

# Check streams
KEYS optimization:*

# Monitor in real-time
MONITOR
```

### Worker Health
Workers log to stdout:
```bash
# Check worker logs
./backend/api/start_worker.sh

# Output shows:
# - Jobs picked up
# - Job completion
# - Errors
```

---

## Production Deployment

### Docker Example
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv && \
    uv pip install --system -r requirements.txt

# API Server
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# OR Worker
# CMD ["arq", "backend.api.workers.main.WorkerSettings"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  api:
    build: .
    command: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
  
  worker:
    build: .
    command: arq backend.api.workers.main.WorkerSettings
    environment:
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 3  # Run 3 workers
    depends_on:
      - redis
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: optimization-worker
spec:
  replicas: 5  # Run 5 workers across cluster
  template:
    spec:
      containers:
      - name: worker
        image: autoroad-api:latest
        command: ["arq", "backend.api.workers.main.WorkerSettings"]
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
```

---

## Troubleshooting

### No workers picking up jobs
```bash
# Check Redis connection
redis-cli PING

# Check worker is running
ps aux | grep arq

# Check worker logs
./backend/api/start_worker.sh
```

### Jobs timing out
- Increase `job_timeout` in `backend/api/workers/main.py`
- Increase `max_time_in_seconds` for CP-SAT solver
- Add more workers

### High memory usage
- Reduce `max_jobs` per worker
- Run more workers with fewer jobs each
- Clear old Redis streams periodically

---

## API Documentation

Interactive docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
