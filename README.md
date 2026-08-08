# Inspect-Vision

Inspect-Vision is a manufacturing image-inspection application with a React/Vite
frontend, FastAPI backend, OpenCV preprocessing, selectable defect-detection
models, SQLite history, annotated image output, live-frame inspection, quality
scoring, and CSV export.

The operator registry exposes one broad anomaly localizer and two independent
specialists:

- **General Manufacturing (Bayes-PFL)** — category-guided cross-domain anomaly localization;
- **Steel Surface** — six-class steel defect specialist;
- **Concrete & Structural Cracks** — crack specialist for concrete, masonry, walls, and floors.

These are not modes of one network. They use different independently trained
weights and intentionally remain manually selectable so the same image can be
compared with the general model and a specialist.

## Requirements

- Git;
- Python 3.13;
- Node.js with npm;
- enough disk space for the Python environment, model artifacts, and inspection media.

CUDA is optional. The tracked Python dependencies use CPU PyTorch by default.
The full Bayes-PFL path requires a 934 MB CLIP backbone plus a 110 MB Bayes-PFL
checkpoint, so its first installation is a little over 1 GB before environment
overhead.

## Fresh-clone setup

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

Install backend dependencies and create the backend environment file:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

### Full default setup

Install the Bayes-PFL default:

```bash
python scripts/install_models.py
```

The installer downloads the pinned `train_visa.pth` checkpoint, the pinned
OpenAI CLIP `ViT-L-14-336px.pt` backbone, and the minimal pinned Bayes-PFL
runtime source set. Artifacts are verified by expected byte size and SHA-256.
No external model repository clone is required.

Install every currently exposed model:

```bash
python scripts/install_models.py --all
```

### Lightweight specialist-only setup

To bring the application up without the >1 GB Bayes-PFL download, install one
of the smaller specialists first:

```bash
python scripts/install_models.py --model neu-defect-yolov8
# or
python scripts/install_models.py --model concrete-crack-yolov8
```

The UI falls back to an installed model when the manifest default is not yet
installed. Bayes-PFL can be added later with:

```bash
python scripts/install_models.py --model bayespfl-general-v1
```

If a model host returns a timeout, HTML confirmation/captcha page, wrong byte
count, or wrong digest, the installer prints the source URL, destination path,
expected size, SHA-256, and exact retry command so the artifact can be placed
manually instead of failing with an opaque download traceback.

Model `.pt` and `.pth` files are intentionally ignored by Git.

Install frontend dependencies:

```bash
npm --prefix frontend ci
```

The frontend uses the real backend by default. Use `frontend/.env.example` only
when a local override is needed.

## Run

Backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend in a second terminal:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at
`http://localhost:8000/docs`.

## Current model artifacts

| Operator model | Backend | Artifact | Size | SHA-256 | Domain / native output |
| --- | --- | --- | ---: | --- | --- |
| General Manufacturing (Bayes-PFL) | Bayes-PFL + CLIP | `train_visa.pth` | 109,523,051 B | `b3d89b6a6018679e44f413ce4cb0931626bedbd480829d6fba94f2176f270fc3` | cross-domain localization / `anomaly` |
| General Manufacturing (Bayes-PFL) | CLIP | `ViT-L-14-336px.pt` | 934,088,680 B | `3035c92b350959924f9f00213499208652fc7ea050643e8b385c2dac08641f02` | visual/text backbone |
| Steel Surface | Ultralytics YOLOv8 | `defect_neu_yolov8.pt` | 6,257,194 B | `635402c435786756c000694654271f1e6aee3eb039aa5e975bb8ec8e9ec0e34b` | NEU steel / six named steel classes |
| Concrete & Structural Cracks | Ultralytics YOLOv8 | `crack_detection.pt` | 22,522,595 B | `386155cae09bee6af1ce99608fc42a32cafd40a25362b80037b4fa54f6999719` | structural surfaces / `crack` |

The full source URLs, revisions, license scope, thresholds, preprocessing, and
quality weights are in `backend/models/model-manifest.json`.

## Why `train_visa.pth` is intentional

Bayes-PFL publishes cross-dataset checkpoints. The filename describes the
**auxiliary training domain**, not the dataset that should be used to demonstrate
zero-shot behavior.

Inspect-Vision intentionally uses:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification / showcase domain: MVTec AD
protocol: held-out cross-dataset zero-shot
```

The current operator samples `bottle`, `capsule`, `screw`, and `metal_nut` are
MVTec AD categories, so `train_visa.pth` keeps them outside the checkpoint's
auxiliary training domain. Replacing it with `train_mvtec.pth` while continuing
to qualify on those MVTec categories would defeat this cross-dataset protocol.

This relationship is also machine-readable in
`backend/detection/model-selection.json`. Repository tests reject a model
selection state where the Bayes auxiliary training and qualification domains
collapse to the same value.

## Product / category context

Bayes-PFL uses the product/category text as CLIP prompt context. It is **not** a
whitelist of classes on which the target product must have been trained. An
incorrect or meaningless prompt can still produce a valid embedding and a
successful HTTP response while degrading localization, including silent false
negatives. For that reason the UI provides curated suggestions while still
allowing custom zero-shot categories.

Current curated examples:

| Evidence level | Product/category examples |
| --- | --- |
| Locally checked with the current Bayes-PFL path | Bottle, Capsule, Screw, Metal nut |
| Additional upstream MVTec examples | Hazelnut, Pill, Toothbrush, Tile, Wood, Carpet |
| General-vs-specialist comparison domains | Steel surface, Concrete surface |

`Cable` and `Zipper` are intentionally absent from the curated list because the
local candidate checks were unacceptable. They can still be entered as custom
zero-shot context if someone explicitly wants to experiment.

The server normalizes category input to lowercase, accepts `_` as a backwards-
compatible space separator, and requires 2-40 characters, Latin letters/spaces/
hyphens, and at most three words. Invalid input returns HTTP 422 for both
`/api/inspect` and `/api/stream`.

Model and category controls are independent. Choosing `Steel surface` does not
automatically select the steel specialist, and choosing `Concrete surface` does
not automatically select the crack specialist. This is deliberate: an operator
can run the same source through Bayes-PFL and then manually choose the relevant
specialist to compare the general and domain-specific behavior.

## Why Bayes-PFL returns `anomaly`

Bayes-PFL is used as an anomaly localizer. Its native application output is the
generic type `anomaly`; Inspect-Vision does not fabricate labels such as
`scratch` or `dent` when the model did not classify them. The steel and concrete
specialists preserve their own semantic checkpoint-native classes. History type
filters are built from the currently exposed model registry, so `anomaly`, steel
classes, and `crack` appear without hard-coding retired model classes.

## Model selection history

`backend/detection/model-selection.json` is the tracked selection record. It
separates models that remain operator-selectable from candidates retained only
for historical reproducibility.

| Candidate | Decision | Reason retained in the project |
| --- | --- | --- |
| Bayes-PFL | **Selected general** | Best fit among the checked broad anomaly-localization candidates; requires meaningful category context |
| NEU YOLOv8 | **Selected specialist** | Narrow steel detector with six native steel-defect classes |
| Concrete crack YOLOv8 | **Selected specialist** | Narrow detector for visible structural cracks |
| `factory-defect-guard-v6-mc` | **Rejected general** | Local cross-domain checks showed unreliable coverage and class confusion; checkpoint remains registered but `exposed: false` |
| YOLO-World X | **Rejected candidate** | Local candidate checks showed poor localization, oversized boxes, and false positives on clean images |
| AnomalyCLIP | **Rejected candidate** | Local cross-domain checks mixed successful cases with misses, false positives, and overly broad anomaly regions |

Historical AnomalyCLIP runtime material under `docs/evidence/` remains immutable.
The legacy factory YOLO checkpoint is likewise retained in the manifest so old
experiments can still be reproduced explicitly, but a tracked consistency check
prevents a rejected registered model from becoming operator-visible again.

## Inspection flow

```text
JPEG/PNG bytes
-> content validation and OpenCV decode
-> selected model + optional guided product context
-> original-coordinate native detections
-> annotated image + quality score + verdict
-> SQLite metadata + original/annotated media
```

Ultralytics models use the shared letterbox path. Bayes-PFL owns its 518x518
stretch, CLIP normalization, anomaly-map postprocessing, and coordinate
restoration, preventing a second geometry transform in the shared service.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/models` | List currently selectable models, curated Bayes category examples, and installed/default state |
| `GET` | `/api/samples` | List the attributed MVTec AD good/bad showcase catalog |
| `GET` | `/api/samples/{id}/image` | Proxy one pinned showcase source image |
| `POST` | `/api/inspect` | Inspect and persist an image |
| `POST` | `/api/stream` | Inspect one JPEG frame without persistence |
| `GET` | `/api/history` | List/filter inspections |
| `GET` | `/api/history/{id}` | Read one inspection with image data URLs |
| `DELETE` | `/api/history/{id}` | Delete one inspection and owned media |
| `POST` | `/api/history/clear` | Clear inspection history and owned media |
| `GET` | `/api/export` | Export filtered history as CSV |

Bayes-PFL example:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "modelId=bayespfl-general-v1" \
  -F "productName=Capsule" \
  -F "image=@path/to/capsule.png;type=image/png"
```

The complete request/response contract is in `docs/api-contract.md`.

## Samples

The operator Samples page contains eight held-out MVTec AD entries:

```text
Bottle      GOOD / BAD
Capsule     GOOD / BAD
Screw       GOOD / BAD
Metal nut   GOOD / BAD
```

The catalog is pinned to MMAD mirror revision
`e88b7bd615ad582b0a7e8238066a9fb293a072b4`. MVTec AD is licensed
CC BY-NC-SA 4.0. To avoid silently redistributing another dataset snapshot in
this repository, the application stores the pinned catalog/provenance and
proxies image bytes from that revision when a sample is opened. This means the
Samples page needs network access for source images.

Clicking a sample automatically supplies that sample's product/category context
but **does not change the selected detection model**. Source labels are dataset
metadata, never cached model predictions.

The separate tracked VisA demo corpus under `backend/samples/demo/` remains a
source-truth/legacy verification corpus and is not used as current Bayes-PFL
zero-shot qualification evidence.

## Quality score and bonuses

The backend returns an integer `qualityScore` from 0 to 100. Higher values mean
better quality. It is an application heuristic based on defect class,
confidence, count, and bbox area; it is not calibrated metrology or a safety
measurement.

The project also implements live camera/frame inspection through
`POST /api/stream`, backend-authoritative quality scoring, and server-side CSV
export.

## Project structure

```text
backend/
  detection/       detector adapters, selection metadata, prompt validation
  models/          model manifest and local ignored model artifacts
  routes/          FastAPI API boundaries
  samples/         demo/showcase catalogs and provenance
  storage/         SQLite and media lifecycle
frontend/
  src/             React routes, components, context, API client, mocks, styles
  tests/           frontend utility/model tests
docs/               contracts, status, verification records
scripts/            installation, validation, reproducible runtime probes
tests/              Python unit and integration tests
```

## Validation and runtime evidence

Run repository checks from an activated environment:

```bash
python scripts/validate.py
```

Useful focused commands:

```bash
python scripts/validate_showcase_samples.py
python scripts/validate_architecture.py
python -m pytest
npm --prefix frontend test
npm --prefix frontend run build
```

Real-model qualification is a separate step:

```bash
python scripts/probe_models.py --device cpu
```

Runtime evidence is never rewritten to match code that it did not execute. If
detector-bound source changes, the previous runtime bundle remains historical
and `docs/project-status.json` records that requalification is pending. Only an
actually executed production-service probe can replace that pending state with a
new current runtime record.

Repository navigation and ownership rules are in `AGENTS.md`. Current capability
status is in `docs/project-status.json`, and requirement-to-check mapping is in
`docs/verification.md`.
