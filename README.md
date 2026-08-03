# Inspect-Vision

Visual quality-control system for manufacturing images. The React/Vite frontend,
selected-model inspection service, crash-recoverable SQLite/media persistence,
and main FastAPI inspection/history API are implemented and verified. Live
stream, server CSV, and the final ten-image demo dataset remain planned.

## Current state

- Frontend routes, upload UI, history, Canvas overlays, severity fallback, live
  capture UI, and CSV integration are implemented.
- Real API mode is the default (`VITE_USE_MOCK=false`).
- Two local Ultralytics detection models are registered by source revision,
  license, SHA-256, input size, and native classes; `.pt` files remain ignored.
- The Python core accepts a BGR `numpy.ndarray` and returns normalized multiclass
  detections with `class_id`, `class_name`, `confidence`, and input-image `xyxy`
  coordinates.
- `DetectionService` owns the production inspection path: 640-square letterbox,
  grayscale, CLAHE, three-channel YOLO input, one original-coordinate restore,
  six-class identity mapping, positive-area filtering, original-size annotation,
  `quality-v1`, and the passed/failed verdict.
- SQLite metadata, combined server-side filters, staged media creation,
  quarantined deletion, failure compensation, and restart reconciliation are
  implemented.
- FastAPI loads one detector/service during lifespan, serializes inference, and
  implements upload plus history list/detail/delete/clear.
- Original media is stored byte-for-byte; annotation uses the same detected
  JPEG/PNG format; POST/detail use the dual-image data URL contract.
- `/api/stream` and `/api/export` are not implemented yet.
- The authoritative limitations and baseline SHA are in
  `docs/project-status.json`.

## Python setup

Inspect-Vision uses Python 3.13.5 on Windows. From Git Bash:

```bash
python --version
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-api.txt
```

The API profile includes the exact CPU detection profile. Install a compatible
CUDA PyTorch build separately before selecting `cuda` or `cuda:N`. For
detection-only work, install `requirements-detection.txt` instead.

Model weights must match `backend/models/model-manifest.json`. Verify both local
models through the detection core with:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --engine core --device cpu --confidence 0.05
```

Run the selected model through the complete inspection service at production
confidence and regenerate JSON plus annotated PNG evidence with:

```bash
.venv/Scripts/python.exe scripts/probe_inspection_service.py
```

Run the real selected model through a loopback Uvicorn server, POST/list/detail/
delete persistence sequence, and regenerate HTTP JSON evidence with:

```bash
.venv/Scripts/python.exe scripts/probe_api_persistence.py
```

## Run

Copy `.env.example` to `.env`, keep the registered model weight at the configured
path, then start the backend from the repository root:

```bash
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another Git Bash terminal:

```bash
cd frontend
npm ci
npm run dev
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
make probe-service
make probe-api
make status
```

Without Make:

```bash
.venv/Scripts/python.exe scripts/validate_structure.py
.venv/Scripts/python.exe scripts/validate_architecture.py
.venv/Scripts/python.exe scripts/generate_dependency_graph.py --check
.venv/Scripts/python.exe -m pytest tests/unit/backend_api tests/unit/contracts tests/unit/detection tests/unit/history tests/unit/evidence tests/integration/api
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
