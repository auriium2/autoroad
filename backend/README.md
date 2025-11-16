# Autoroad Backend

Course schedule optimizer using CP-SAT (Constraint Programming SAT solver).

## Architecture

- **FastAPI** server for HTTP endpoints
- **Server-Sent Events (SSE)** for real-time progress streaming
- **OR-Tools CP-SAT** for constraint solving
- **Threading** for async optimization execution

## Features

### Constraint Builders
- **Requirements**: GIRs, major requirements (from Fireroad API)
- **Prerequisites**: Course prerequisite chains
- **Markers**: User-defined constraints (pin, banish, solo)

### Objective Functions
All normalized to ~100 per course for balanced weighting:
- **MinimizeUnits**: Prefer fewer total units
- **MaximizeRating**: Prefer highly-rated courses (target 6.0)
- **MaximizeWeightedRating**: Bayesian-weighted ratings
- **MinimizeTotalHours**: Minimize total weekly hours
- **MinimizeMaxSemesterHours**: Soft constraint on hours per semester
- **FrontloadCourses**: Prefer earlier semesters
- **BackloadCourses**: Prefer later semesters
- **MinimizeFridayClasses**: Avoid Friday classes
- **ClusterCourses**: Minimize gaps between classes
- **MaximizeCohortOverlap**: Prefer larger class sizes
- **MinimizeFinalsLoad**: Soft constraint on finals per semester

See `optimizer/objectives/SCALES.md` for scaling details.

## Setup

### Prerequisites
- Python 3.11+
- uv (Python package manager)

### Install Dependencies
```bash
cd backend
uv sync
```

## Running

### Development Mode

Start the FastAPI server:
```bash
uv run uvicorn api.main:app --reload --port 8000 --log-level info
```

Note: SSE streaming works best without buffering. If you experience delayed responses, try:
```bash
uv run uvicorn api.main:app --reload --port 8000 --timeout-keep-alive 300
```

### Production Mode

Use gunicorn with uvicorn workers:
```bash
uv run gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## API Endpoints

### POST /api/optimize
Start optimization job and stream progress via SSE.

**Request:**
```json
{
  "markers": [
    {
      "courseId": "6.100A",
      "section": 0,
      "status": "pin"
    }
  ],
  "requirements": ["girs", "major6-3new"],
  "constraints": {
    "maxSemesters": 12,
    "maxUnitsPerSemester": 60,
    "maxUnitsIAP": 12,
    "maxHoursPerSemester": 60
  },
  "planningYear": "2026-2027"
}
```

**Response:** SSE stream with messages:
- `progress`: Status updates (e.g., "Creating model...", "Adding requirements...")
- `solution`: New solution found (intermediate results as solver improves)
- `complete`: Optimization finished (includes final status and warnings)
- `error`: Error occurred

### POST /api/optimize/clear-cache
Clear cached course and requirement data from Fireroad API.

## Testing

Run unit tests:
```bash
uv run pytest
```

Run specific test:
```bash
uv run python scripts/test_markers.py
```

Run full optimization example:
```bash
uv run python scripts/optimize_with_markers.py
```

## Development

### Type Checking
```bash
uv run basedpyright
```

### Code Structure
```
backend/
├── api/
│   ├── main.py              # FastAPI app
│   ├── routes/              # API endpoints
│   ├── models/              # Pydantic models
│   ├── services/            # Redis, caching
│   └── workers/             # arq background workers
├── optimizer/
│   ├── requirement_constraint_builder.py
│   ├── prerequisite_constraint_builder.py
│   ├── marker_constraint_builder.py
│   └── objectives/          # Objective functions
├── courses/
│   ├── requirements/        # Requirement parsing/validation
│   └── prerequisites/       # Prerequisite parsing/validation
├── utils/
│   └── utils.py             # Helper functions
└── scripts/                 # Test/example scripts
```

## Environment Variables

```bash
# API settings
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
```

## Troubleshooting

### Optimization infeasible
Common causes:
- Conflicting markers (pin same course to multiple semesters)
- Over-constrained requirements
- Marker for course not offered in that semester

Check optimization warnings in response.

### Type errors
Run type checker:
```bash
uv run basedpyright
```

## Performance

Typical optimization times:
- GIRs only: 0.5-1s
- GIRs + major (6-3): 1-3s
- GIRs + major + heavy markers: 3-10s

The solver enumerates multiple solutions and streams them in real-time.
Use `max_time_in_seconds` parameter to limit solve time.

## Contributing

1. Run type checker: `uv run basedpyright`
2. Run tests: `uv run pytest`
3. Ensure all constraint builders have tests
4. Document new objectives in `optimizer/objectives/SCALES.md`
