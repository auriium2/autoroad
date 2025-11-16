# Autoroad

Constraint-based course schedule optimizer for MIT students.

## Quick Start

### Backend
```bash
cd backend
uv sync
uv run uvicorn api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Visit http://localhost:3000

## Architecture

### Frontend
- **Next.js/React** for UI
- **Fireroad API** for course data (via CORS, no auth needed)
- **Server-Sent Events (SSE)** for real-time optimization progress
- Focus on simplicity and LLM-friendliness

### Backend
- **FastAPI** for HTTP endpoints
- **OR-Tools CP-SAT** for constraint solving
- **Modular constraint builders**: requirements, prerequisites, markers
- **Composable objective functions**: minimize units, maximize ratings, frontload, etc.
- Designed for horizontal scalability (stateless, no Redis/workers needed)

## Features

- ✅ **GIR and major requirements** (from Fireroad API)
- ✅ **Prerequisite constraints** (automatic dependency resolution)
- ✅ **User markers** (pin, banish, solo courses)
- ✅ **Multiple objectives** (units, ratings, hours, frontload/backload, etc.)
- ✅ **Real-time streaming** (see solutions as optimizer improves)
- ✅ **Normalized scaling** (all objectives weighted equally)

## Development

See detailed docs:
- [Backend README](backend/README.md)
- [Objective Scaling](backend/optimizer/objectives/SCALES.md)

## AI Usage
- Frontend built entirely with AI assistance (ChatGPT + Copilot)
- Backend unit testing and regression testing by AI
- No human should be forced to write unit tests
- Please employ me
