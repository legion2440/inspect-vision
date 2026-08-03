# Inspect-Vision

Visual quality-control system for manufacturing images. The React/Vite frontend
and reusable multiclass detection core are implemented and runtime-verified.
FastAPI, inspection preprocessing/service logic, persistence, and end-to-end
application evidence remain planned.

## Current state

- Frontend routes, upload UI, history, Canvas overlays, severity fallback, live
  capture UI, and CSV integration are implemented.
- Real API mode is the default (`VITE_USE_MOCK=false`).
- Two local Ultralytics detection models are registered by source revision,
  license, SHA-256, input size, and native classes; `.pt` files remain ignored.
- The Python core accepts a BGR `numpy.ndarray` and returns normalized multiclass
  detections with `class_id`, `class_name`, `confidence`, and original-image
  `xyxy` coordinates.
- Backend endpoints, grayscale/CLAHE service preprocessing, annotation, severity,
  and persistence are not implemented yet.
- The authoritative limitations and baseline SHA are in
  `docs/project-status.json`.

## Python setup

Inspect-Vision uses Python 3.13.5 on Windows. From Git Bash:

```bash
python --version
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-detection.txt
```

The tracked dependency profile installs CPU PyTorch for a reproducible baseline.
Install a compatible CUDA PyTorch build separately before selecting `cuda` or
`cuda:N`.

Model weights must match `backend/models/model-manifest.json`. Verify both local
models through the detection core with:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --engine core --device cpu --confidence 0.05
```

## Commands

```bash
.venv/Scripts/python.exe scripts/validate.py
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
.venv/Scripts/python.exe scripts/validate_structure.py
.venv/Scripts/python.exe scripts/validate_architecture.py
.venv/Scripts/python.exe scripts/generate_dependency_graph.py --check
.venv/Scripts/python.exe -m pytest tests/unit/detection tests/unit/evidence
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
.venv/Scripts/python.exe scripts/show_status.py
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
