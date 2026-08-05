# Inspect-Vision

Inspect-Vision is a manufacturing image-inspection application. A React/Vite
interface sends images plus an optional model selection to a FastAPI backend,
the resolved Ultralytics detector
detects surface defects, OpenCV produces an annotated image, and SQLite plus
owned media storage provide searchable inspection history.

## Requirements

- Windows 11 with Git Bash;
- Python 3.13.5;
- Node.js and npm;
- enough disk space for Python packages, the chosen checkpoints (about 51 MB for
  all three), and
  local inspection media.

The tracked `.pt` files are intentionally excluded from Git.

## Fresh-clone setup

Run these commands from Git Bash:

```bash
git clone https://01.tomorrow-school.ai/git/nyestaye/inspect-vision.git
cd inspect-vision

py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-api.txt

cp .env.example .env
.venv/Scripts/python.exe scripts/install_models.py
```

Without arguments the installer reads `defaultModelId` from
`backend/models/model-manifest.json`. Use `--model <id>` for one specialist or
`--all` for all exposed models. Hidden candidates require an explicit
`--model <id>`. Every download uses an immutable revision,
checks byte size and SHA-256, and is atomically installed only after validation.

Install and configure the frontend:

```bash
cp frontend/.env.example frontend/.env
npm --prefix frontend ci
```

The default frontend configuration uses the real API through relative `/api`
requests. Vite proxies them to `http://localhost:8000` during development.
`VITE_API_BASE_URL` is only needed when a production frontend calls a different
origin. Set `VITE_USE_MOCK=true` only for explicit standalone UI work.

## Run

Start the backend from the repository root:

```bash
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second Git Bash terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at
`http://localhost:8000/docs`.

CUDA is optional. The supplied dependency profile uses CPU PyTorch; install a
compatible CUDA PyTorch build separately before setting
`INSPECT_VISION_MODEL_DEVICE=cuda` or `cuda:N`.

## Configuration

Backend settings use the `INSPECT_VISION_` prefix and are documented in
`docs/env-model-contract.md`. Environment settings contain the shared model
directory/device, CORS origins, SQLite/media paths, and upload limit. Per-model
thresholds, profiles, and quality weights live only in the tracked manifest.
`INSPECT_VISION_MAX_UPLOAD_BYTES` may be lowered but cannot exceed the hard
10 MiB maximum (`10485760` bytes).

## Detection models

General Manufacturing is the coverage-oriented default when the process or
material is not yet known. Steel Surface and Concrete & Structural Cracks are
specialists and should be preferred for their named domains. The registry does
not claim that the broad model is more accurate; runtime probes record its
actual observations without turning them into benchmark claims.

Trusted Ultralytics detect checkpoints can be added by extending the validated
manifest with pinned provenance, native classes, a preprocessing profile, and
quality configuration, then qualifying the result through the same production
manager/service path.

The production inspection path is:

```text
JPEG/PNG bytes -> validated BGR -> one square letterbox
-> standard-color OR steel grayscale + CLAHE -> selected YOLO inference
-> original-coordinate native boxes -> annotation
-> quality score/status -> SQLite record and original/annotated media
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/models` | List registry metadata and installed/default state |
| `GET` | `/api/samples` | List attributed offline showcase metadata |
| `GET` | `/api/samples/{id}/image` | Read one original showcase image by manifest ID |
| `POST` | `/api/inspect` | Inspect and persist `image` with optional `modelId` |
| `POST` | `/api/stream` | Inspect JPEG `frame` with optional `modelId`, without persistence |
| `GET` | `/api/history` | List records with `from`, `to`, `type`, and `q` filters |
| `GET` | `/api/history/{id}` | Read one record with original and annotated data URLs |
| `DELETE` | `/api/history/{id}` | Delete metadata and owned media |
| `POST` | `/api/history/clear` | Clear all metadata and owned media |
| `GET` | `/api/export` | Export the filtered history projection as UTF-8 CSV |

The complete request, response, filtering, image, and error contracts are in
`docs/api-contract.md`.

The Samples page contains nine attributed CC BY 4.0 images across PCB, steel,
and concrete/crack domains. Dataset labels are shown as source metadata only.
Inspecting a sample uses the currently selected model, performs fresh inference
through `/api/inspect`, and stores the result in normal history. The selector is
also available above Quick Upload on the Dashboard.

### Real inspection example

With the backend running, inspect one of the tracked demo images:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "modelId=neu-defect-yolov8" \
  -F "image=@backend/samples/demo/visa-chewinggum-normal-000.jpg;type=image/jpeg"
```

This response was recorded from that image with the steel specialist. Only the
two base64 bodies are shortened here:

```json
{
  "inspectionId": "insp_20260804T054824288330Z_2df23070",
  "timestamp": "2026-08-04T05:48:24.288330Z",
  "fileName": "visa-chewinggum-normal-000.jpg",
  "imageWidth": 1342,
  "imageHeight": 1118,
  "defects": [
    {
      "type": "patches",
      "confidence": 0.46318528056144714,
      "boundingBox": {
        "x": 368.910888671875,
        "y": 283.77960205078125,
        "width": 573.1429443359375,
        "height": 172.46771240234375
      }
    }
  ],
  "totalDefects": 1,
  "qualityScore": 93,
  "status": "failed",
  "model": { "id": "neu-defect-yolov8", "displayName": "Steel Surface" },
  "imageUrl": "data:image/jpeg;base64,<base64 omitted>",
  "originalImageUrl": "data:image/jpeg;base64,<base64 omitted>"
}
```

Demo source labels and model observations are intentionally separate; this
example describes runtime behavior and is not an accuracy claim.

### Real history example

Query the record using the same server-side type filter used by CSV export:

```bash
curl -sS "http://localhost:8000/api/history?type=patches"
```

The corresponding response contains the same persisted fields but no image
payloads:

```json
[
  {
    "inspectionId": "insp_20260804T054824288330Z_2df23070",
    "timestamp": "2026-08-04T05:48:24.288330Z",
    "fileName": "visa-chewinggum-normal-000.jpg",
    "imageWidth": 1342,
    "imageHeight": 1118,
    "defects": [
      {
        "type": "patches",
        "confidence": 0.46318528056144714,
        "boundingBox": {
          "x": 368.910888671875,
          "y": 283.77960205078125,
          "width": 573.1429443359375,
          "height": 172.46771240234375
        }
      }
    ],
    "totalDefects": 1,
    "qualityScore": 93,
    "status": "failed",
    "model": { "id": "neu-defect-yolov8", "displayName": "Steel Surface" }
  }
]
```

## Folder structure

```text
backend/
  detection/       preprocessing orchestration, annotation, scoring, detector DTOs
  models/          tracked model registry; local .pt checkpoints are ignored
  routes/          FastAPI inspect, stream, history, image, and export boundaries
  samples/         attributed demo images and source provenance
  storage/         SQLite repository and consistent media lifecycle
frontend/
  src/             React routes, components, context, API client, mocks, and styles
docs/               API/environment contracts, verification status, runtime evidence
scripts/            model installation, validation, and reproducible runtime probes
tests/              Python unit and integration coverage
```

## Validation

The canonical Windows command runs structure, dataset, architecture, dependency,
Python, frontend, production-build, and dependency-vulnerability checks:

```bash
.venv/Scripts/python.exe scripts/validate.py
```

Useful individual commands:

```bash
.venv/Scripts/python.exe scripts/validate_structure.py
.venv/Scripts/python.exe scripts/validate_architecture.py
.venv/Scripts/python.exe scripts/generate_dependency_graph.py --check
.venv/Scripts/python.exe scripts/validate_demo_samples.py
.venv/Scripts/python.exe scripts/validate_showcase_samples.py
.venv/Scripts/python.exe -m pytest
npm --prefix frontend test
npm --prefix frontend run build
.venv/Scripts/python.exe scripts/check_frontend_dependencies.py
```

Check the fresh backend template without creating a local runtime database:

```bash
.venv/Scripts/python.exe -c "from backend.config import Settings; print(Settings(_env_file='.env.example').max_upload_bytes)"
```

Validate the locally installed default or all exposed models without
downloading verified files again:

```bash
.venv/Scripts/python.exe scripts/install_models.py
.venv/Scripts/python.exe scripts/install_models.py --all
```

Repository navigation and ownership rules are in `AGENTS.md`; current capability
status and executable evidence links are in `docs/project-status.json` and
`docs/verification.md`.
