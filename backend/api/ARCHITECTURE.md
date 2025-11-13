# Autoroad API Architecture

## System Overview

A scalable, production-ready FastAPI backend for MIT course planning optimization using constraint programming (CP-SAT).

### Key Design Decisions

1. **Redis-based Job Queue (arq)**
   - Separates API server from CPU-intensive optimization
   - Horizontally scalable workers
   - Non-blocking API (no request timeouts)

2. **Server-Sent Events (SSE) for Streaming**
   - Real-time progress updates
   - Better UX than polling
   - Works over standard HTTP

3. **CP-SAT releases GIL**
   - Multiple jobs can run concurrently per worker
   - True parallelism despite Python GIL
   - `enumerate_all_solutions` disables internal multi-threading but enables streaming

4. **Two-Phase Cancellation**
   - Abort queued jobs immediately (arq)
   - Signal running jobs via Redis flag (checked on each solution)
   - Responsive cancellation (~1-2 seconds)

---

## Architecture Diagram

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       │ POST /api/optimize
       │ (Returns SSE stream)
       ▼
┌─────────────────┐
│  FastAPI Server │
│   (Port 8000)   │
└────────┬────────┘
         │
         │ 1. Enqueue job
         │ 2. Stream from Redis
         ▼
    ┌────────┐
    │ Redis  │
    │ Queue  │
    │ Stream │
    └───┬────┘
        │
        │ Workers poll for jobs
        ▼
┌─────────────────┐
│  arq Worker 1   │ ◄─── max_jobs=2 concurrent optimizations
│  (Process)      │
└─────────────────┘
┌─────────────────┐
│  arq Worker 2   │ ◄─── Run on same or different machine
│  (Process)      │
└─────────────────┘
┌─────────────────┐
│  arq Worker N   │ ◄─── Scale to N workers
│  (Process)      │
└─────────────────┘
```

---

## Request Flow

### 1. Client Submits Optimization

```
Client → POST /api/optimize
         ├─ Generate job_id (UUID)
         ├─ Fetch course data (cached, 1hr TTL)
         ├─ Fetch requirements (cached, 1hr TTL)
         └─ Enqueue job to arq
```

### 2. Worker Picks Up Job

```
Worker → Dequeue from Redis
         ├─ Build CP-SAT model
         ├─ Add constraints
         │   ├─ Requirements (GIRs, major, etc)
         │   ├─ Prerequisites
         │   ├─ Units per semester
         │   └─ User markers (pins, banish)
         └─ Solve with callback
             └─ On each solution:
                 ├─ Check cancellation flag
                 ├─ Publish to Redis Stream
                 └─ Continue solving
```

### 3. API Streams Results

```
API → Read from Redis Stream
      └─ Yield SSE messages:
          ├─ job_started (with job_id)
          ├─ progress (status updates)
          ├─ solution (course placements)
          └─ complete (final status)
```

---

## Scaling Strategy

### Horizontal Scaling (Recommended)

**Run multiple worker processes:**

```bash
# Machine 1 (8 cores)
./start_worker.sh  # Worker 1: max_jobs=2
./start_worker.sh  # Worker 2: max_jobs=2
./start_worker.sh  # Worker 3: max_jobs=2
./start_worker.sh  # Worker 4: max_jobs=2
# Total: 8 concurrent optimizations

# Machine 2 (8 cores) - point to same Redis
export REDIS_HOST=redis.example.com
./start_worker.sh  # Worker 5
./start_worker.sh  # Worker 6
# Total: 12 concurrent optimizations
```

### Vertical Scaling (Per Worker)

```python
# workers/main.py
class WorkerSettings:
    max_jobs = 4  # Increase from 2 to 4
```

**Trade-offs:**
- Higher `max_jobs` = more concurrent jobs per worker
- But: more memory usage per worker
- Recommendation: `max_jobs = 2-4` for typical workloads

---

## Performance Characteristics

### Latency
- **Queue time**: ~10-50ms (if workers available)
- **Model building**: ~1-2 seconds
- **Solving**: 20-40 seconds (typical MIT course load)
- **Total**: ~25-45 seconds per optimization

### Throughput
- **Single worker** (`max_jobs=2`): ~4 jobs/minute
- **4 workers** (`max_jobs=2`): ~16 jobs/minute
- **10 workers** (`max_jobs=2`): ~40 jobs/minute

### Resource Usage (per worker)
- **CPU**: 200% (2 cores at 100% when running max_jobs=2)
- **Memory**: ~500MB-1GB
- **Network**: ~10KB/s to Redis (for streaming)

---

## Key Components

### 1. Cache Layer (`services/cache.py`)
```python
@cached(cache=_courses_cache, lock=_courses_lock)
def get_courses_data() -> List[Dict]:
    # TTL: 1 hour
    # Fetches from Fireroad API
```

**Purpose:** Minimize external API calls, reduce latency

### 2. Job Queue (`workers/main.py`)
```python
class WorkerSettings:
    max_jobs = 2
    job_timeout = 300  # 5 minutes
```

**Purpose:** Decouple API from compute, enable scaling

### 3. Streaming Callback (`workers/optimizer_worker.py`)
```python
class RedisStreamCallback(cp_model.CpSolverSolutionCallback):
    def on_solution_callback(self):
        # Check cancellation
        # Publish to Redis Stream
```

**Purpose:** Real-time progress updates, cancellation support

### 4. API Routes (`routes/optimize.py`)
```python
POST   /api/optimize          # Start job, stream results
DELETE /api/optimize/{job_id} # Cancel job
POST   /api/optimize/clear-cache
```

**Purpose:** HTTP interface to optimization service

---

## Cancellation Mechanism

### Two-Phase Cancellation

**Phase 1: Abort Queued Jobs**
```python
job = Job(job_id, redis_pool)
await job.abort()  # Immediate if not started
```

**Phase 2: Signal Running Jobs**
```python
await redis_client.set(f"cancel:{job_id}", "1")

# In callback:
if cancel_flag:
    self.StopSearch()  # CP-SAT stops at next solution
```

**Responsiveness:**
- Queued jobs: Immediate (never start)
- Running jobs: 1-2 seconds (at next solution)

---

## Data Flow

### Optimization Request
```json
{
  "markers": [
    {"courseId": "6.1200", "section": 1, "status": "pin"}
  ],
  "requirements": ["major6-3new", "girs"],
  "constraints": {
    "maxSemesters": 12,
    "maxUnitsPerSemester": 60,
    "maxUnitsIAP": 12
  }
}
```

### SSE Events
```
data: {"type": "job_started", "job_id": "abc-123"}

data: {"type": "progress", "message": "Building model...", "step": 1}

data: {"type": "solution", "nodes": [...], "semesterUnits": [...]}

data: {"type": "complete", "status": "OPTIMAL", "solutionCount": 15}
```

---

## Failure Modes & Recovery

### Worker Crashes
- Job marked as failed in Redis
- Client receives timeout after 60s
- Other workers continue processing queue

### Redis Failure
- Workers cannot pick up jobs
- API cannot enqueue jobs
- Graceful degradation: Return error to client

### Long-Running Jobs
- Timeout: 5 minutes (configurable)
- CP-SAT timeout: 20 seconds (configurable)
- Client timeout: 60 seconds

### Network Disconnection
- SSE connection drops
- Job continues running in background
- Client can reconnect or cancel via job_id

---

## Future Enhancements

1. **Job Results Persistence**
   - Store completed solutions in Redis/DB
   - Allow retrieval after SSE stream ends

2. **Priority Queue**
   - Premium users get higher priority
   - Configurable via `_queue_name` in arq

3. **Metrics & Monitoring**
   - Job duration tracking
   - Worker health checks
   - Redis queue depth monitoring

4. **Rate Limiting**
   - Per-user job limits
   - Global throughput caps

5. **Result Caching**
   - Cache solutions for identical requests
   - TTL-based invalidation

6. **Multi-threading Mode**
   - Optional: Disable streaming, enable `num_search_workers`
   - Faster single-job latency
   - Trade-off: No progress updates
