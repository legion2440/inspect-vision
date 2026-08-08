# Inspect-Vision

Inspect-Vision is a manufacturing image-inspection application with a React/Vite
frontend, FastAPI backend, OpenCV preprocessing, selectable defect-detection
models, SQLite history, annotated image output, live-frame inspection, quality
scoring, and CSV export.

The default detector is category-guided Bayes-PFL. Steel and concrete models are
available as specialists, and a legacy multiclass YOLO model remains selectable
for broader class-labelled coverage.

## Requirements

- Git;
- Python 3.13;
- Node.js with npm;
- enough disk space for the Python environment, model artifacts, and inspection
  media. Installing every exposed model requires a little over 1 GB of model
  files.

CUDA is optional. The tracked Python dependencies use CPU PyTorch by default.

## Fresh-clone setup

Clone the repository:

```bash
git clone https://01.tomorrow-school.ai/git/nyestaye/inspect-vision.git
cd inspect-vision
```

Create and activate a virtual environment.

Linux / macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Git Bash:

```bash
py -3.13 -m venv .venv
source .venv/Scripts/activate
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
```

Create the backend environment file.

Linux / macOS / Git Bash:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Install the default model:

```bash
python scripts/install_models.py
```

No external model repository clone is required. The installer reads
`backend/models/model-manifest.json`, downloads the pinned Bayes-PFL checkpoint
and CLIP backbone, verifies byte size and SHA-256, and only then moves each file
into `backend/models`.

Other installation options:

```bash
# one model
python scripts/install_models.py --model neu-defect-yolov8

# every exposed model
python scripts/install_models.py --all
```

Model `.pt` and `.pth` files are intentionally ignored by Git.

Install frontend dependencies:

```bash
npm --prefix frontend ci
```

The tracked frontend configuration uses the real backend by default. Copy the
frontend template only when you need a local override:

Linux / macOS / Git Bash:

```bash
cp frontend/.env.example frontend/.env
```

PowerShell:

```powershell
Copy-Item frontend/.env.example frontend/.env
```

## Run

Start FastAPI from the repository root:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at
`http://localhost:8000/docs`.

The Vite development server proxies relative `/api` requests to
`http://localhost:8000`. `VITE_API_BASE_URL` is only needed when the frontend
must call another origin. `VITE_USE_MOCK=true` enables the explicit standalone
frontend mock mode.

## Detection models

| Model ID | UI name | Role | Native output |
| --- | --- | --- | --- |
| `bayespfl-general-v1` | General Manufacturing (Bayes-PFL) | default general | `anomaly` |
| `factory-defect-guard-v6-mc` | General Manufacturing (YOLO) | general | 17 checkpoint-native classes |
| `neu-defect-yolov8` | Steel Surface | specialist | 6 steel defect classes |
| `concrete-crack-yolov8` | Concrete & Structural Cracks | specialist | `crack` |

Bayes-PFL requires a product/category name such as `capsule`, `screw`, or
`metal_nut`. This context is sent as multipart field `productName`. The model is
an anomaly localizer: it produces the native generic type `anomaly`, not an
invented semantic defect subtype.

The production Bayes-PFL adapter uses the pinned upstream inference settings:
518×518 bicubic stretch, CLIP normalization, feature layers 6/12/18/24,
10 flows, deterministic seed 333, Gaussian sigma 8, application map threshold
0.72, minimum component area ratio 0.0005, and 25% bbox padding. The fixed
threshold and bbox conversion are application settings rather than an upstream
accuracy claim.

When the material is known and a supported specialist exists, prefer the
specialist. The steel and concrete models preserve their own native classes and
preprocessing profiles.

## Inspection flow

```text
JPEG/PNG bytes
-> content validation and OpenCV decode
-> selected model runtime
-> original-coordinate native detections
-> annotated image + quality score + verdict
-> SQLite metadata + original/annotated media
```

Ultralytics models use the shared letterbox path. Bayes-PFL owns its 518×518
stretch, anomaly-map postprocessing, and coordinate restoration, preventing a
second geometry transform in the shared service.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/models` | List selectable models and installed/default state |
| `GET` | `/api/samples` | List attributed showcase metadata |
| `GET` | `/api/samples/{id}/image` | Read one showcase source image |
| `POST` | `/api/inspect` | Inspect and persist an image |
| `POST` | `/api/stream` | Inspect one JPEG frame without persistence |
| `GET` | `/api/history` | List/filter inspections |
| `GET` | `/api/history/{id}` | Read one inspection with image data URLs |
| `DELETE` | `/api/history/{id}` | Delete one inspection and owned media |
| `POST` | `/api/history/clear` | Clear inspection history and owned media |
| `GET` | `/api/export` | Export filtered history as CSV |

`POST /api/inspect` accepts multipart field `image`, optional `modelId`, and
`productName` when required by the selected model. `POST /api/stream` uses
`frame` plus the same model fields. Omitting `modelId` selects the manifest
default, currently Bayes-PFL, so `productName` is required in that case.

Example:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "modelId=bayespfl-general-v1" \
  -F "productName=capsule" \
  -F "image=@path/to/capsule.png;type=image/png"
```

The complete request, response, filtering, image, and error contract is in
`docs/api-contract.md`.

## Samples

The Samples page contains nine attributed CC BY 4.0 images across PCB, steel,
and concrete/crack domains. Dataset labels are displayed as source metadata,
not model predictions. Selecting a sample performs fresh inference through the
ordinary `/api/inspect` workflow and stores the result in history.

Sample recommendations do not silently switch the global model selection.

## Quality score and bonuses

The backend returns an integer `qualityScore` from 0 to 100. Higher values mean
better quality. The score is an application heuristic based on defect class,
confidence, count, and bbox area; it is not calibrated metrology or a safety
measurement.

The project also implements:

- live camera/frame inspection through `POST /api/stream`;
- backend-authoritative quality scoring;
- server-side CSV export through `GET /api/export`.

## Configuration

Backend environment settings use the `INSPECT_VISION_` prefix and are documented
in `docs/env-model-contract.md`. Environment configuration owns runtime paths,
device selection, CORS, and the upload limit. Model thresholds, preprocessing,
native classes, artifact hashes, and quality weights live in
`backend/models/model-manifest.json`.

`INSPECT_VISION_MAX_UPLOAD_BYTES` may be lowered but cannot exceed 10 MiB.

## Project structure

```text
backend/
  detection/       detector adapters, geometry ownership, annotation, scoring
  models/          model manifest and local ignored model artifacts
  routes/          FastAPI API boundaries
  samples/         attributed demo/showcase assets and provenance
  storage/         SQLite and media lifecycle
frontend/
  src/             React routes, components, context, API client, mocks, styles
  tests/           frontend utility/model tests
docs/               contracts, status, verification records
scripts/            installation, validation, reproducible runtime probes
tests/              Python unit and integration tests
```

## Validation

Run the repository checks from an activated virtual environment:

```bash
python scripts/validate.py
```

The suite checks repository structure, sample manifests, architecture rules,
dependency graph drift, Python unit/integration tests, frontend tests, the Vite
production build, and frontend dependency security state.

Useful individual commands:

```bash
python scripts/validate_structure.py
python scripts/validate_architecture.py
python scripts/generate_dependency_graph.py --check
python scripts/validate_demo_samples.py
python scripts/validate_showcase_samples.py
python -m pytest
npm --prefix frontend test
npm --prefix frontend run build
python scripts/check_frontend_dependencies.py
```

To exercise installed models through the production runtime/service pipeline:

```bash
python scripts/probe_models.py --device cpu
```

Runtime probes record actual observations; they do not convert those observations
into benchmark-accuracy claims.

Repository navigation and ownership rules are in `AGENTS.md`. Current capability
status is in `docs/project-status.json`, and requirement-to-check mapping is in
`docs/verification.md`.
