# Autoroad Backend: Google Cloud Run Serverless Deployment Analysis

## Executive Summary

The Autoroad backend is **partially compatible** with serverless deployment to Google Cloud Run, with significant architectural considerations that require careful planning. The main challenges are:

1. **Long-running optimization solver** (30-second timeout limit)
2. **Real-time SSE streaming** (5-minute connection limit on Cloud Run)
3. **In-memory caching with TTL** (ephemeral container state)
4. **File I/O** (writes optimization results to local filesystem)
5. **Threading usage** (potential issues with serverless cold starts)

This analysis identifies all incompatibilities and provides detailed mitigation strategies.

---

## Part 1: Current Server Setup & Dependencies

### 1.1 Framework Stack

**Framework: FastAPI**
- File: `/Users/matt/summer/autoroad/backend/api/main.py`
- Version: `>=0.121.1`
- Server: `uvicorn>=0.38.0`
- Status: COMPATIBLE (pure Python async framework, no external dependencies)

```python
# Current setup - simple and clean
app = FastAPI(title="Autoroad API", version="1.0.0")
app.add_middleware(CORSMiddleware, ...)
```

**Endpoints:**
- `POST /api/optimize` - Main optimization with SSE streaming
- `GET /api/optimize/objectives` - List available objectives
- `GET /api/optimize/requirements` - Fetch requirement definitions
- `POST /api/optimize/clear-cache` - Clear caches
- `GET /health` - Health check
- `GET /` - Root endpoint

### 1.2 Dependencies

From `/Users/matt/summer/autoroad/backend/pyproject.toml`:

```toml
dependencies = [
    "requests>=2.32.0",           # HTTP requests to Fireroad API
    "pandas>=2.0.0",              # Data manipulation for course data
    "ortools>=9.0.0",             # Google OR-Tools (CP-SAT solver)
    "basedpyright>=1.33.0",       # Type checking
    "pyarrow>=22.0.0",            # Arrow data format support
    "fastapi>=0.121.1",           # Web framework
    "uvicorn>=0.38.0",            # ASGI server
    "cachetools>=6.2.2",          # In-memory TTL caching
]
```

**Compatibility Assessment:**
- ✓ `requests` - Fully compatible, used for external API calls
- ✓ `pandas` - Fully compatible, data processing library
- ⚠ `ortools` - Fully compatible BUT contains compute-heavy operations
- ✓ `pyarrow` - Fully compatible
- ✓ `fastapi` - Fully compatible
- ✓ `uvicorn` - Cloud Run handles ASGI internally
- ⚠ `cachetools` - Compatible BUT relies on in-memory state (ephemeral)

**Total Size Estimate:** ~400MB+ (ortools + pandas are large)

---

## Part 2: Stateful Components & Serverless Incompatibilities

### 2.1 In-Memory Caching (MAJOR ISSUE)

**File:** `/Users/matt/summer/autoroad/backend/api/services/cache.py`

Current implementation uses thread-safe TTL caches:

```python
_courses_cache: TTLCache[str, list[dict[str, object]]] = TTLCache(maxsize=1, ttl=3600)
_courses_lock = threading.RLock()

_requirements_cache: TTLCache[str, dict[str, object]] = TTLCache(maxsize=128, ttl=3600)
_requirements_lock = threading.RLock()

@cached(cache=_courses_cache, lock=_courses_lock)
def get_courses_data() -> list[dict[str, object]]:
    """Cached for 1 hour"""
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    return [c for c in response.json() if not c.get('is_historical')]
```

**Problems with Serverless:**
1. Cache is **lost between requests** - each Cloud Run container instance is ephemeral
2. New instances created during scaling will make fresh API calls to Fireroad
3. Multiple concurrent instances = redundant API calls
4. No persistence across cold starts

**Impact:**
- Repeated calls to Fireroad API (increased latency and network cost)
- Potential rate-limiting from Fireroad if many instances are created
- Higher costs due to multiple external API calls per optimization

**Mitigation Required:**
- Move to distributed cache: Cloud Memorystore (Redis)
- Or: Use Cloud Datastore with TTL
- Or: Accept increased API calls (simpler, but higher latency)

### 2.2 File I/O Operations (MAJOR ISSUE)

**File:** `/Users/matt/summer/autoroad/backend/api/routes/optimize.py` (lines ~330-350)

Code writes optimization results to local filesystem:

```python
road_data = {
    "coursesOfStudy": [],
    "progressAssertions": {},
    "selectedSubjects": [...]
}

output_path = Path("optimization_result.road")
with open(output_path, "w") as f:
    json.dump(road_data, f, indent=2)
print(f"[SSE] Exported best solution to {output_path}")
```

**Problems with Serverless:**
1. Cloud Run filesystem is **ephemeral** - files disappear when container stops
2. No persistent storage mounted by default
3. Multiple instances will overwrite each other's files
4. Results are **not accessible** after container shutdown

**Impact:**
- Optimization results are lost
- Client cannot retrieve `.road` file after request completes
- Breaks any downstream processing that depends on saved files

**Mitigation Required:**
- Use Cloud Storage (GCS) instead of local files
- Upload results to GCS after optimization completes
- Return file URL/metadata in response to client
- Or: Return results directly in SSE response (no file needed)

### 2.3 Thread-Based Solver Execution (MEDIUM ISSUE)

**File:** `/Users/matt/summer/autoroad/backend/api/routes/optimize.py` (lines ~270-290)

```python
def run_solver():
    nonlocal result
    result = solver.Solve(model, callback)
    solution_queue.put({'__done__': True, 'result': result, 'count': callback.solution_count})
    solver_done.set()

solver_thread = threading.Thread(target=run_solver)
solver_thread.start()

# Stream solutions as they arrive
while not solver_done.is_set() or not solution_queue.empty():
    try:
        solution = solution_queue.get(timeout=0.1)
        ...
```

**Problems with Serverless:**
1. Threading adds complexity in async environment
2. Cold starts may be slower due to thread initialization
3. Thread resources are limited in serverless containers
4. Queue-based communication adds latency

**Impact:**
- Marginal (threading will still work)
- Might see longer cold start times
- Could cause issues if Cloud Run's CPU throttling is aggressive

**Mitigation:**
- Consider pure async/await without threading
- Or: Accept the minor overhead (likely acceptable)

---

## Part 3: Long-Running Operations

### 3.1 CP-SAT Solver Timeout (CRITICAL ISSUE)

**Files:**
- `/Users/matt/summer/autoroad/backend/api/routes/optimize.py` (optimization endpoint)
- `/Users/matt/summer/autoroad/backend/optimizer/` (constraint builders)

Current solver configuration:

```python
solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = 30  # 30-second timeout
```

**Solver Characteristics:**
- Builds constraint satisfaction problem (CSP) with OR-Tools CP-SAT
- Adds constraints for:
  - Prerequisites (recursive evaluation of course dependencies)
  - Requirements (major/GIR/HASS satisfaction)
  - Marker constraints (pinned/banished courses)
  - Basic constraints (max units per semester, take each course once)
  - Objective functions (multiple weighted objectives)
- Streams solutions as they're found via callback

**Problems with Serverless:**
1. **Cloud Run timeout:** Default 5 minutes, but can be set up to 60 minutes
2. **Connection timeout:** SSE stream connections have limits
3. **Billing:** Long-running requests = higher costs
4. **Cold start:** 30-60 second cold start + 30 second solve = inefficient

**Current Solver Performance:**
- 30-second timeout with enumeration enabled
- Can find multiple solutions
- Status values: OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID
- Degrades to FEASIBLE if time limit reached

**Mitigation Options:**

**Option A: Accept Serverless Limitations (Recommended for initial MVP)**
- Set Cloud Run timeout to 60 seconds max
- Solver runs 25-30 seconds (with 5-10 second buffer)
- Return best solution found (FEASIBLE status is acceptable)
- Client sees "Solution found but may not be optimal" warning

**Option B: Async Job Queue (Better for Production)**
- Move optimization to Cloud Tasks or Pub/Sub
- Return job ID immediately, client polls for results
- Worker services run optimization asynchronously
- Store results in Firestore/Cloud Storage
- No connection timeout issues

**Option C: Hybrid Approach (Best UX)**
- Keep SSE for real-time progress (< 30 seconds)
- Switch to polling after timeout
- Continue optimization in background
- Return incrementally better solutions

### 3.2 SSE Streaming Connection Limits

**File:** `/Users/matt/summer/autoroad/backend/api/routes/optimize.py`

```python
async def event_stream():
    # ... optimization logic ...
    yield f"data: {json.dumps(progress_msg)}\n\n"
    yield f"data: {json.dumps(solution)}\n\n"
    yield f"data: {json.dumps({'type': 'complete', ...})}\n\n"

return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**Issues:**
1. **Cloud Run HTTP limit:** Default 5 minutes per request
2. **Browser/client limits:** Some proxies may disconnect after 5 minutes
3. **Network conditions:** Slow networks may time out sooner
4. **Container shutdown:** If instance is terminated, connection drops

**Current timeout:** 30 seconds (solver) - within limits but tight margin

**Mitigation:**
- Increase Cloud Run timeout to 60-90 seconds
- Implement client-side reconnection logic
- Send heartbeat messages every 30 seconds
- Or: Use polling instead of SSE for better reliability

---

## Part 4: External Dependencies & API Calls

### 4.1 Fireroad API Integration

**Service Used:**
- URL: `https://fireroad.mit.edu/`
- Endpoints:
  - `GET /courses/all?full=true` - All courses (cached for 1 hour)
  - `GET /requirements/list_reqs` - All requirements
  - `GET /requirements/get_json/{key}` - Specific requirement (cached per key for 1 hour)

**File:** `/Users/matt/summer/autoroad/backend/api/services/cache.py`

```python
def get_courses_data() -> list[dict[str, object]]:
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
    response.raise_for_status()
    data = response.json()
    courses = [c for c in data if not c.get('is_historical')]
    return courses

def get_requirement(key: str) -> dict[str, object]:
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return resp.json()
```

**Serverless Compatibility:**
- ✓ COMPATIBLE - Cloud Run can make outbound HTTPS requests
- ✓ Thread-pool is used for parallel fetching
- ⚠ No retry logic or timeout handling
- ⚠ No fallback if Fireroad is down

**Calls per Optimization Request:**
1. `get_courses_data()` - 1 call (cached)
2. `get_requirements()` - 1+ calls per requirement (cached per requirement)
3. `get_requirements_list()` - 1 additional call (if using objectives endpoint)

**Potential Issues:**
- Fireroad API is external dependency - if down, optimization fails
- No timeouts set on requests (can hang indefinitely)
- No circuit breaker or fallback mechanism
- Cached data may be stale if requirements change

**Recommendations:**
- Add `timeout=10` to all requests
- Implement retry with exponential backoff
- Add circuit breaker pattern for Fireroad API
- Log and monitor API call metrics

---

## Part 5: Environment Configuration & Settings

### 5.1 Current Configuration

**File:** `/Users/matt/summer/autoroad/.env.example`

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:3000/api

# Optional: Authentication
NEXT_PUBLIC_AUTH_ENABLED=false
```

**Analysis:**
- Minimal configuration
- No database connection strings
- No API keys or secrets
- CORS hardcoded in code (localhost:3000, localhost:3001)
- No logging configuration
- No feature flags

### 5.2 Code-Hardcoded Settings

**CORS Configuration** (`/Users/matt/summer/autoroad/backend/api/main.py`):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Solver Parameters** (`/Users/matt/summer/autoroad/backend/api/routes/optimize.py`):
```python
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = 30
```

**Constraints** (`/Users/matt/summer/autoroad/backend/api/models/requests.py`):
```python
class OptimizationConstraints(BaseModel):
    maxSemesters: int = Field(default=12, ge=1, le=12)
    maxUnitsPerSemester: int = Field(default=60, ge=1, le=100)
    maxUnitsIAP: int = Field(default=12, ge=0, le=50)
```

### 5.3 Cloud Run Configuration Needed

**Required Environment Variables:**
```bash
# Cloud Run specific
ENVIRONMENT=production
CLOUD_RUN_TIMEOUT=60
LOG_LEVEL=INFO

# API endpoints
API_URL=https://[your-cloud-run-service].run.app
FIREROAD_API_BASE=https://fireroad.mit.edu

# CORS for production
CORS_ORIGINS=https://[frontend-domain].com

# Optional: Distributed caching
REDIS_URL=redis://[memorystore-instance]:6379
CACHE_TTL_COURSES=3600
CACHE_TTL_REQUIREMENTS=3600

# GCS configuration
GCS_BUCKET=autoroad-results-[project-id]
GCS_ENABLED=true

# Logging and monitoring
SENTRY_DSN=[optional-sentry-url]
GOOGLE_CLOUD_PROJECT=[project-id]
```

---

## Part 6: Background Tasks & Threading Usage

### 6.1 Threading Implementation

**Location:** `/Users/matt/summer/autoroad/backend/api/routes/optimize.py` (lines 270-290)

```python
solver_done = threading.Event()

def run_solver():
    nonlocal result
    result = solver.Solve(model, callback)
    solution_queue.put({'__done__': True, 'result': result, 'count': callback.solution_count})
    solver_done.set()

solver_thread = threading.Thread(target=run_solver)
solver_thread.start()

# Wait for solutions
while not solver_done.is_set() or not solution_queue.empty():
    try:
        solution = solution_queue.get(timeout=0.1)
        # Stream solution
        yield f"data: {json.dumps(solution)}\n\n"
    except queue.Empty:
        await asyncio.sleep(0.05)

solver_thread.join()
```

**Analysis:**
- Single solver thread per request
- Uses queue for inter-thread communication
- Properly waits for thread completion (`join()`)
- Should work fine in serverless

### 6.2 Concurrent Request Handling

**Current:** No background jobs or async queue system
- Each `/api/optimize` request blocks until completion
- Solver runs synchronously within request lifecycle
- No job persistence
- No retry mechanism

**Serverless Implications:**
- ✓ Works for single requests
- ⚠ Multiple concurrent requests = multiple instances scaled up
- ⚠ No state sharing between requests
- ⚠ Long requests prevent quick shutdown

---

## Part 7: File System Writes & Reads

### 7.1 Write Operations

**Location:** `/Users/matt/summer/autoroad/backend/api/routes/optimize.py` (lines ~335-350)

```python
from pathlib import Path

road_data = {
    "coursesOfStudy": [],
    "progressAssertions": {},
    "selectedSubjects": [
        {
            "subject_id": node["courseId"],
            "semester": int(node["section"]) + 1,
            "title": node.get("title", ""),
            "units": 12,
            "overrideWarnings": False
        }
        for node in callback.best_solution_nodes
    ]
}

output_path = Path("optimization_result.road")
with open(output_path, "w") as f:
    json.dump(road_data, f, indent=2)
print(f"[SSE] Exported best solution to {output_path}")
```

**Issues:**
- Writes to relative path `optimization_result.road`
- In Container: Will write to `/Users/matt/summer/autoroad/optimization_result.road` or working directory
- In Cloud Run: Will write to container's `/workspace/optimization_result.road` (ephemeral)
- File is **inaccessible** to client after container stops

### 7.2 Read Operations

**No application-level file reads detected**
- All data comes from external APIs (Fireroad)
- No file-based course database
- No file-based configuration

---

## Part 8: Optimization Components Deep Dive

### 8.1 Objective Functions

**File:** `/Users/matt/summer/autoroad/backend/optimizer/objectives/`

Components found:
- `base.py` - Base class for objectives
- `builder.py` - Compose multiple objectives with weights
- `registry.py` - Registry of available objectives
- `scheduling.py` - Scheduling-related objectives
- `workload.py` - Workload objectives
- `ratings.py` - Course rating objectives
- `social.py` - Social/community objectives
- `units.py` - Unit optimization objectives
- `utils.py` - Utility functions

**Sample from builder.py:**
```python
builder = ObjectiveBuilder()
builder.add(MinimizeUnits(), weight=0.3)
builder.add(MaximizeRating(), weight=0.5)
builder.add(FrontloadCourses(), weight=0.2)

objective = builder.build(model, take_vars, courses_df, planning_year_start)
model.Minimize(objective)
```

**Serverless Implications:**
- ✓ Pure Python computation
- ✓ No external dependencies
- ✓ All objectives loaded in-memory
- ⚠ Complex objective functions increase solver time

### 8.2 Constraint Building

**Files:**
- `requirement_constraint_builder.py` - Requirement satisfaction constraints
- `prerequisite_constraint_builder.py` - Prerequisite enforcement
- `marker_constraint_builder.py` - User-defined course placement

**Key Functions:**
- `add_requirement_constraints()` - Ensures majors/GIRs/HASS satisfied
- `add_prerequisite_constraints()` - Enforces prerequisite chains
- `add_marker_constraints()` - Applies pin/banish/override markers
- `add_basic_constraints()` - Max units, take once per course

**Constraint Count:**
- Prerequisite constraints: ~500-2000+ (depends on course choices)
- Requirement constraints: ~100-500 (depends on requirements)
- Marker constraints: 1-50+ (user-defined)
- Basic constraints: ~200-500 (units + per-course)

**Total: ~1000-3000 constraints** per optimization

**Serverless Implications:**
- ✓ All constraint building is pure Python
- ✓ No external service calls
- ⚠ Constraint building time adds to total latency
- ⚠ Larger constraint sets increase solver time

---

## Deployment Impact Matrix

| Component | Severity | Serverless Impact | Mitigation Effort |
|-----------|----------|-------------------|-------------------|
| **SSE Streaming** | HIGH | 5-min timeout, ephemeral connections | MEDIUM - switch to polling or async jobs |
| **Solver Timeout** | HIGH | 30 sec solve + cold start overhead | MEDIUM - accept FEASIBLE or use job queue |
| **File I/O** | HIGH | Results lost on shutdown | EASY - use Cloud Storage |
| **In-Memory Cache** | MEDIUM | Cache lost between instances | MEDIUM - use Cloud Memorystore |
| **Threading** | LOW | Minor overhead on cold start | LOW - works fine, consider pure async |
| **Fireroad API** | MEDIUM | External dependency, network failures | MEDIUM - add retries and timeouts |
| **CORS Config** | LOW | Hardcoded localhost | EASY - move to environment variables |
| **Solver Complexity** | MEDIUM | Longer cold start, slower responses | HARD - optimize constraints or use caching |

---

## Detailed Recommendations for Cloud Run Deployment

### Immediate Changes (Must Fix)

#### 1. Replace File I/O with Cloud Storage

**Current Code:**
```python
output_path = Path("optimization_result.road")
with open(output_path, "w") as f:
    json.dump(road_data, f, indent=2)
```

**Replacement:**
```python
from google.cloud import storage
import json

def save_optimization_result(job_id: str, data: dict) -> str:
    """Save result to GCS, return public URL"""
    client = storage.Client()
    bucket = client.bucket(os.getenv("GCS_BUCKET", "autoroad-results"))
    
    filename = f"optimizations/{job_id}/result.road"
    blob = bucket.blob(filename)
    blob.upload_from_string(
        json.dumps(data, indent=2),
        content_type="application/json"
    )
    
    # Return signed URL valid for 7 days
    url = blob.generate_signed_url(version="v4", expiration=timedelta(days=7))
    return url
```

**Changes needed:**
- Add `google-cloud-storage>=2.10.0` to dependencies
- Update `.road` file export to use GCS
- Return URL in SSE response
- Update client to download from URL instead of local filesystem

#### 2. Externalize CORS Configuration

**Current Code:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Replacement:**
```python
import os

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Cloud Run Configuration:**
```bash
gcloud run deploy autoroad-backend \
  --set-env-vars CORS_ORIGINS="https://frontend.example.com"
```

#### 3. Add Request Timeouts to Fireroad API

**Current Code:**
```python
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
```

**Replacement:**
```python
response = requests.get(
    'https://fireroad.mit.edu/courses/all?full=true',
    timeout=10  # 10 second timeout
)
```

**Add to all requests.get() calls:**
- `get_courses_data()` - timeout=10
- `fetch_requirement()` - timeout=10
- `get_requirements_list()` endpoint - timeout=10

#### 4. Increase Cloud Run Timeout

**Current:** Default 5 minutes (300 seconds)
**Recommended:** 90 seconds (allows 30s cold start + 60s solver)

```bash
gcloud run deploy autoroad-backend \
  --timeout=90 \
  --max-instances=100
```

### Short-Term Improvements (1-2 weeks)

#### 5. Implement Distributed Caching

**Option A: Google Cloud Memorystore (Redis)**

```python
import redis
import os
from cachetools import cached

redis_url = os.getenv("REDIS_URL")
redis_client = redis.from_url(redis_url) if redis_url else None

def get_courses_data() -> list[dict[str, object]]:
    if redis_client:
        # Check cache
        cached_data = redis_client.get("courses:all")
        if cached_data:
            return json.loads(cached_data)
    
    # Fetch from API
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true', timeout=10)
    courses = [c for c in response.json() if not c.get('is_historical')]
    
    # Store in cache
    if redis_client:
        redis_client.setex(
            "courses:all",
            3600,  # 1 hour TTL
            json.dumps(courses)
        )
    
    return courses
```

**Setup:**
```bash
# Create Memorystore instance
gcloud memorystore instances create autoroad-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=7.0

# Get instance IP
gcloud memorystore instances describe autoroad-cache \
  --region=us-central1 --format='value(host)'

# Deploy with Redis URL
gcloud run deploy autoroad-backend \
  --set-env-vars REDIS_URL="redis://10.0.0.3:6379"
```

**Option B: Firestore with TTL (Simpler, no VPC needed)**

```python
from google.cloud import firestore
import json

db = firestore.Client()

def get_courses_data() -> list[dict[str, object]]:
    # Check Firestore cache
    doc = db.collection("cache").document("courses_all").get()
    if doc.exists and not doc.get("_expired"):
        return doc.get("data")
    
    # Fetch from API
    response = requests.get('https://fireroad.mit.edu/courses/all?full=true', timeout=10)
    courses = [c for c in response.json() if not c.get('is_historical')]
    
    # Store with TTL
    from datetime import datetime, timedelta
    db.collection("cache").document("courses_all").set({
        "data": courses,
        "timestamp": datetime.now(),
        "expires": datetime.now() + timedelta(hours=1)
    }, merge=True)
    
    return courses
```

#### 6. Implement Async Job Queue (Future-proof)

This enables longer-running optimizations:

**Option A: Cloud Tasks (Simple, recommended)**

```python
from google.cloud import tasks_v2
import json
import uuid

def enqueue_optimization(request: OptimizationRequest) -> dict:
    """Enqueue optimization job, return job ID"""
    job_id = str(uuid.uuid4())
    
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        os.getenv("GOOGLE_CLOUD_PROJECT"),
        "us-central1",
        "optimization-queue"
    )
    
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{os.getenv('API_URL')}/api/optimize/process/{job_id}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(request.model_dump()).encode()
        }
    }
    
    client.create_task(request={"parent": parent, "task": task})
    
    return {"job_id": job_id, "status": "queued"}

@app.post("/api/optimize/job")
async def optimize_job(request: OptimizationRequest):
    """Enqueue optimization instead of running synchronously"""
    return enqueue_optimization(request)

@app.get("/api/optimize/job/{job_id}")
async def get_job_result(job_id: str):
    """Poll for job result"""
    db = firestore.Client()
    doc = db.collection("optimization_jobs").document(job_id).get()
    
    if not doc.exists:
        return {"status": "not_found"}
    
    return doc.to_dict()
```

**Option B: Pub/Sub + Cloud Run (More scalable)**

- POST to `/api/optimize` publishes to Pub/Sub
- Separate Cloud Run service subscribes and processes
- Results stored in Firestore
- Client polls for results

### Medium-Term Improvements (1-2 months)

#### 7. Implement Health Checks & Logging

```python
import logging
from pythonjsonlogger import jsonlogger

# Setup structured logging
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

@app.get("/health")
async def health():
    """Cloud Run health check"""
    try:
        # Check Fireroad API connectivity
        requests.head('https://fireroad.mit.edu', timeout=5)
        api_status = "healthy"
    except Exception as e:
        logger.error(f"Fireroad API check failed: {e}")
        api_status = "degraded"
    
    # Check cache connectivity (if Redis)
    if redis_client:
        try:
            redis_client.ping()
            cache_status = "healthy"
        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            cache_status = "unhealthy"
    else:
        cache_status = "not_configured"
    
    return {
        "status": "healthy" if api_status == "healthy" else "degraded",
        "api": api_status,
        "cache": cache_status,
        "timestamp": datetime.now().isoformat()
    }
```

#### 8. Add Monitoring & Error Tracking

```python
# Add Sentry for error tracking
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment=os.getenv("ENVIRONMENT", "development")
)

# Add Cloud Trace integration
from google.cloud.trace_v2 import TraceServiceClient
```

#### 9. Optimize Solver Performance

```python
# Consider reducing timeout or solution enumeration for web requests
solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = int(
    os.getenv("SOLVER_TIMEOUT", "25")  # Leave 5s buffer for streaming
)

# Add solver statistics logging
solver.parameters.log_search_progress = True
```

### Long-Term Improvements (2+ months)

#### 10. Switch to Async/Await (Remove Threading)

Current threading is unnecessary with async/await:

```python
@router.post("/optimize")
async def optimize(request: OptimizationRequest):
    """Run optimization and stream progress via SSE."""
    
    async def event_stream():
        loop = asyncio.get_event_loop()
        
        # Load data asynchronously
        courses_data = await loop.run_in_executor(None, get_courses_data)
        requirements_data = await loop.run_in_executor(None, get_requirements, tuple(request.requirements))
        
        # Build model asynchronously
        model, take_vars = await loop.run_in_executor(None, create_model, courses_data)
        
        # Run solver without threading
        # Use ProcessPoolExecutor for CPU-intensive CP-SAT
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = loop.run_in_executor(executor, lambda: solve_model(model, ...))
            result = await future
```

#### 11. Consider Separation of Concerns

**Current:** Single monolithic endpoint handles everything
**Better:** Separate services:
- Frontend UI service (Next.js on Vercel)
- Optimization API (Cloud Run)
- Result storage (Cloud Storage)
- Job queue service (Cloud Tasks/Pub/Sub)
- Caching layer (Cloud Memorystore)

---

## Deployment Checklist

### Pre-Deployment

- [ ] Add Cloud Storage client library to dependencies
- [ ] Add request timeouts to all Fireroad API calls
- [ ] Move CORS origins to environment variables
- [ ] Move solver timeout to environment variables
- [ ] Add health check endpoint with dependency checks
- [ ] Replace local file writes with Cloud Storage
- [ ] Add structured logging
- [ ] Create `.dockerignore` to exclude unnecessary files
- [ ] Test locally with environment variables

### GCP Setup

- [ ] Create Google Cloud project
- [ ] Enable Cloud Run API
- [ ] Enable Artifact Registry
- [ ] Create Cloud Storage bucket (for results)
- [ ] Create Cloud Memorystore instance (optional, for caching)
- [ ] Set up Cloud Build for CI/CD
- [ ] Configure IAM roles for Cloud Run service account
- [ ] Create secrets in Secret Manager for sensitive data

### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install uv && uv pip install --system -r requirements.txt

# Copy source code
COPY backend/ ./

# Set environment
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Run with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Deployment Command

```bash
# Build and deploy
gcloud run deploy autoroad-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --timeout=90 \
  --memory=2Gi \
  --cpu=2 \
  --max-instances=100 \
  --min-instances=0 \
  --set-env-vars "ENVIRONMENT=production,CORS_ORIGINS=https://yourdomain.com,GCS_BUCKET=autoroad-results-prod" \
  --service-account=autoroad-backend@your-project.iam.gserviceaccount.com
```

---

## Cost Estimation

### Monthly Costs (Estimated)

**Current Local Setup:**
- ~$0 (self-hosted)

**Cloud Run (Conservative Estimate):**
- 1,000 optimizations/month
- 30 seconds per optimization
- 1000 seconds × 30 = 30,000 seconds = 8.3 hours
- CPU: 2 vCPU × 8.3 hours = 16.6 vCPU-hours ≈ **$0.80/month**
- Memory: 2 GiB × 8.3 hours = 16.6 GiB-hours ≈ **$0.70/month**
- Requests: 1,000 × $0.20/million = **$0.0002/month**

**Cloud Memorystore (if used):**
- Basic tier 1 GB instance ≈ **$35/month**

**Cloud Storage:**
- 1,000 results × 10 KB = 10 MB
- 10 MB × $0.020/GB = **<$0.01/month**

**Total: ~$37/month** (with caching)
**Total: ~$1.50/month** (without caching)

---

## Risk Assessment

### High Risk Items

1. **SSE Streaming Timeout**
   - Impact: Optimization results not received by client
   - Probability: Medium (will happen under slow networks)
   - Mitigation: Switch to polling or async jobs

2. **Solver Takes >60 Seconds**
   - Impact: Cloud Run timeout, no results returned
   - Probability: Low (30s timeout usually sufficient)
   - Mitigation: Monitor solver time, adjust constraints if needed

3. **Fireroad API Down**
   - Impact: All optimizations fail
   - Probability: Low (but external dependency)
   - Mitigation: Add fallback cached data, health checks

### Medium Risk Items

1. **Cold Starts (2-3 seconds)**
   - Impact: Higher latency, worse user experience
   - Mitigation: Enable min-instances=1 (+$10/month)

2. **Cache Inconsistency**
   - Impact: Stale course/requirement data
   - Probability: Low (1-hour TTL acceptable)
   - Mitigation: Monitor cache hit rates, log misses

3. **Concurrent Request Scaling**
   - Impact: Higher costs, potential quota exceeded
   - Mitigation: Set max-instances, monitor metrics

### Low Risk Items

1. **Threading Issues** - Unlikely to cause problems
2. **Library Compatibility** - All libraries support Python 3.10
3. **Network Connectivity** - Cloud Run has good egress

---

## Conclusion

**Autoroad backend is DEPLOYABLE to Google Cloud Run** with the following caveats:

**Must Fix (Critical):**
1. Replace file I/O with Cloud Storage
2. Add request timeouts to Fireroad API calls
3. Externalize CORS configuration
4. Increase Cloud Run timeout to 90 seconds

**Should Fix (Important):**
5. Implement distributed caching (Memorystore or Firestore)
6. Add health checks and structured logging
7. Consider async job queue for longer optimizations

**Nice to Have (Polish):**
8. Switch to pure async/await without threading
9. Separate concerns into microservices
10. Add comprehensive monitoring and error tracking

**Timeline:** 
- MVP deployment: 1-2 weeks (with critical fixes)
- Production-ready: 1-2 months (with all improvements)

The current 30-second solver timeout is actually beneficial for serverless, as it keeps response times short. The main challenge is ensuring results are persistent (GCS) and handling the occasional slow network case (polling as fallback).

**Recommendation:** Start with the critical fixes, deploy to Cloud Run, monitor for issues, then implement improvements based on real usage patterns.
