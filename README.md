# Inspect-Vision

Inspect-Vision is a manufacturing image-inspection application. A React/Vite
interface sends images to a FastAPI backend, the selected Ultralytics model
detects surface defects, OpenCV produces an annotated image, and SQLite plus
owned media storage provide searchable inspection history.

## Requirements

- Windows 11 with Git Bash;
- Python 3.13.5;
- Node.js and npm;
- enough disk space for Python packages, the selected 6.3 MB checkpoint, and
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
.venv/Scripts/python.exe scripts/install_selected_model.py
```

The installer reads `selectedModelId` from
`backend/models/model-manifest.json`, downloads its immutable revision, checks
the declared byte size and SHA-256, and only then installs the checkpoint. It
does not change the selected model or download registered alternatives.

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
`docs/env-model-contract.md`. The main values are the model path/device,
confidence and IoU thresholds, CORS origins, SQLite/media paths, and upload
limit. `INSPECT_VISION_MAX_UPLOAD_BYTES` may be lowered but cannot exceed the
hard 10 MiB maximum (`10485760` bytes).

The production inspection path is:

```text
JPEG/PNG bytes -> validated BGR -> 640-square letterbox -> grayscale -> CLAHE
-> 3-channel YOLO inference -> original-coordinate boxes -> annotation
-> quality score/status -> SQLite record and original/annotated media
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/inspect` | Inspect and persist multipart field `image` |
| `POST` | `/api/stream` | Inspect a JPEG multipart field `frame` without persistence |
| `GET` | `/api/history` | List records with `from`, `to`, `type`, and `q` filters |
| `GET` | `/api/history/{id}` | Read one record with original and annotated data URLs |
| `DELETE` | `/api/history/{id}` | Delete metadata and owned media |
| `POST` | `/api/history/clear` | Clear all metadata and owned media |
| `GET` | `/api/export` | Export the filtered history projection as UTF-8 CSV |

The complete request, response, filtering, image, and error contracts are in
`docs/api-contract.md`.

### Real inspection example

With the backend running, inspect one of the tracked demo images:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "image=@backend/samples/demo/visa-chewinggum-normal-000.jpg;type=image/jpeg"
```

This response was recorded from that image with the selected model at the
default confidence. Only the two base64 bodies are shortened here:

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
  "model": { "name": "neu-defect-yolov8", "version": "1" },
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
    "model": { "name": "neu-defect-yolov8", "version": "1" }
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
.venv/Scripts/python.exe -m pytest
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
```

Check the fresh backend template without creating a local runtime database:

```bash
.venv/Scripts/python.exe -c "from backend.config import Settings; print(Settings(_env_file='.env.example').max_upload_bytes)"
```

Validate the locally installed selected checkpoint without downloading it again:

```bash
.venv/Scripts/python.exe scripts/install_selected_model.py
```

Repository navigation and ownership rules are in `AGENTS.md`; current capability
status and executable evidence links are in `docs/project-status.json` and
`docs/verification.md`.
