# Inspect-Vision

Visual quality-control system for manufacturing images. The React/Vite frontend
is implemented and build-verified. The FastAPI, OpenCV, model, persistence, and
runtime-evidence modules are intentionally marked `planned` until implemented
and verified.

## Current state

- Frontend routes, upload UI, history, Canvas overlays, severity fallback, live
  capture UI, and CSV integration are implemented.
- Real API mode is the default (`VITE_USE_MOCK=false`).
- Backend endpoints and real model inference are not implemented yet.
- The authoritative limitations and baseline SHA are in
  `docs/project-status.json`.

## Commands

```bash
python scripts/validate.py
```

If GNU Make is installed, the same checks are available as:

```bash
make validate
make validate-architecture
make validate-frontend
make test
make architecture
make check-architecture
make status
```

Without Make:

```bash
python scripts/validate_structure.py
python scripts/validate_architecture.py
python scripts/generate_dependency_graph.py --check
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
python scripts/show_status.py
```

Frontend development:

```bash
cd frontend
npm ci
npm run dev
```

Copy `frontend/.env.example` to `frontend/.env`. Real API mode remains the
default; set `VITE_USE_MOCK=true` only for explicit standalone UI work.

Read `AGENTS.md` before changing the repository. Architecture, API, environment,
model, and audit contracts live under `docs/`.
