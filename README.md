# Inspect-Vision

Inspect-Vision is a manufacturing image-inspection application with a React/Vite frontend, FastAPI backend, OpenCV preprocessing, selectable defect-detection models, SQLite history, annotated image output, live-frame inspection, quality scoring, and CSV export.

The operator can choose between one broad category-guided anomaly localizer and two smaller domain specialists. The general model is useful when the product class varies and the task is to find unusual regions; the specialists are preferable inside their known domains when the defect type itself matters.

· [Русская версия](README_RU.md)

## 📋 TOC

- [🚀 Quick start](#-quick-start)
- [📝 About](#-about)
- [🧠 Model strategy](#-model-strategy)
- [📦 Model artifacts](#-model-artifacts)
- [🧭 Model selection history](#-model-selection-history)
- [🏷️ Product / category context](#️-product--category-context)
- [🖼️ Samples](#️-samples)
- [🔄 Inspection flow](#-inspection-flow)
- [🔌 API](#-api)
- [🎯 Quality score and extras](#-quality-score-and-extras)
- [🧪 Tests and verification](#-tests-and-verification)
- [📁 Project structure](#-project-structure)
- [⚠️ Notes](#️-notes)
- [🧑‍💻 Author](#-author)

## 🚀 Quick start

### Requirements

- Git
- Python 3.13
- Node.js with npm
- enough disk space for the Python environment, model artifacts, and inspection media
- optional NVIDIA CUDA or Apple MPS acceleration

### Clone

```bash
git clone https://01.tomorrow-school.ai/git/nyestaye/inspect-vision.git
cd inspect-vision
```

### Python environment

Windows Git Bash:

```bash
py -3.13 -m venv .venv
source .venv/Scripts/activate
```

Linux / macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

### Choose the PyTorch compute build

Inspect-Vision pins PyTorch `2.12.1` and torchvision `0.27.1` without forcing a CPU-only wheel. Install the build that matches the machine before the remaining backend dependencies.

Windows or Linux with NVIDIA CUDA 12.6:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1 \
  --index-url https://download.pytorch.org/whl/cu126
```

Windows or Linux, CPU only:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1 \
  --index-url https://download.pytorch.org/whl/cpu
```

macOS, including Apple Silicon:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1
```

On macOS, `auto` uses MPS when available. Optional PyTorch operation fallback:

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

Install the remaining backend and frontend dependencies:

```bash
python -m pip install -r requirements-api.txt
cp .env.example .env
npm --prefix frontend ci
```

Verify the selected compute backend:

```bash
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('mps:', bool(getattr(torch.backends, 'mps', None)) and torch.backends.mps.is_available())"
```

The default runtime policy is:

```text
INSPECT_VISION_MODEL_DEVICE=auto
```

`auto` resolves `CUDA -> MPS -> CPU`. Explicit `cpu`, `cuda`, `cuda:N`, and `mps` are also supported. An explicitly requested unavailable accelerator fails instead of silently falling back.

### Install models

Install the default Bayes-PFL general model:

```bash
python scripts/install_models.py
```

Install every exposed model:

```bash
python scripts/install_models.py --all
```

A lightweight specialist-only installation can avoid the approximately 1.04 GB Bayes-PFL + CLIP download:

```bash
python scripts/install_models.py --model neu-defect-yolov8
# or
python scripts/install_models.py --model concrete-crack-yolov8
```

Bayes-PFL can be added later:

```bash
python scripts/install_models.py --model bayespfl-general-v1
```

Artifacts are checked by expected size and SHA-256. Model `.pt` and `.pth` files are intentionally ignored by Git.

### Run

Backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend in a second Git Bash terminal:

```bash
npm --prefix frontend run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at `http://localhost:8000/docs`.

## 📝 About

The application provides:

- manual model selection across Dashboard, Inspect, live stream, and Samples;
- category-guided general anomaly localization;
- steel and concrete domain specialists;
- persisted inspection history with original and annotated media;
- defect bounding boxes in original-image coordinates;
- backend-authoritative quality scoring;
- CSV export;
- non-persisted live-frame inspection;
- an attributed operator sample catalog for general-vs-specialist comparison.

The real FastAPI backend is the default frontend data source. Mock inference must be enabled explicitly and does not hide backend/model failures.

## 🧠 Model strategy

The three exposed models solve different problems. A larger model is not automatically a better specialist.

| Operator model | Role | Scope | Native output | Approx. model download | Best use |
| --- | --- | --- | --- | ---: | --- |
| General Manufacturing (Bayes-PFL) | broad guided localizer | multiple product categories with text context | `anomaly` | ~1.04 GB with CLIP | find suspicious regions when the exact domain-specific defect taxonomy is unknown |
| Steel Surface | specialist | steel surfaces | six named steel-defect classes | ~6.3 MB | identify the concrete steel defect class inside its trained domain |
| Concrete & Structural Cracks | specialist | concrete, masonry, walls, floors | `crack` | ~22.5 MB | detect visible structural cracks inside its trained domain |

The practical trade-off is deliberate:

- **Bayes-PFL is broad but semantically generic.** It can localize an anomalous region across different product categories, but its application output is only `anomaly`. If it sees a damaged area, Inspect-Vision does not pretend that the model knows whether it is a scratch, dent, inclusion, crack, or another specific defect.
- **The specialists are narrow but semantically more useful inside their domains.** The steel model returns its six checkpoint-native defect classes, while the concrete model returns `crack`.
- **The specialists are dramatically smaller.** The steel checkpoint is about 6.3 MB and the concrete checkpoint about 22.5 MB, versus roughly 1.04 GB for the Bayes-PFL checkpoint plus CLIP backbone.
- **A matching specialist is the preferred semantic detector.** Bayes-PFL remains useful as a broad anomaly localizer and for side-by-side comparison on the same source image.

Model and category selection are independent on purpose. Selecting `Steel surface` does not silently switch to the steel model, and selecting `Concrete surface` does not silently switch to the crack model.

### Why `train_visa.pth` is intentional

Bayes-PFL publishes cross-dataset checkpoints. Inspect-Vision uses:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification / showcase domain: MVTec AD
protocol: held-out cross-dataset zero-shot
```

The operator Bayes samples are MVTec AD categories, so using `train_visa.pth` keeps the qualification domain distinct from the checkpoint's auxiliary training domain. Switching to `train_mvtec.pth` while qualifying on MVTec would defeat that protocol.

The relationship is also stored in `backend/detection/model-selection.json`, and repository checks prevent the auxiliary training and qualification domains from collapsing to the same value.

### Runtime device behavior

`DetectionRuntimeManager` lazy-loads and caches one successful `DetectionService` per model. For guided Bayes-PFL requests, changing `Bottle`, `Capsule`, `Screw`, `Metal nut`, or another category updates the prompt context without loading another full Bayes-PFL/CLIP copy.

That means an accelerator run has two distinct phases:

- the first request after process start can be noticeably slower because the model is loaded and initialized;
- subsequent warm requests reuse the cached model, so CUDA/MPS acceleration is not hidden by repeated model startup.

## 📦 Model artifacts

| Operator model | Backend | Artifact | Size | SHA-256 | Domain / native output |
| --- | --- | --- | ---: | --- | --- |
| General Manufacturing (Bayes-PFL) | Bayes-PFL | `train_visa.pth` | 109,523,051 B | `b3d89b6a6018679e44f413ce4cb0931626bedbd480829d6fba94f2176f270fc3` | cross-domain localization / `anomaly` |
| General Manufacturing (Bayes-PFL) | CLIP | `ViT-L-14-336px.pt` | 934,088,680 B | `3035c92b350959924f9f00213499208652fc7ea050643e8b385c2dac08641f02` | visual/text backbone |
| Steel Surface | Ultralytics YOLOv8 | `defect_neu_yolov8.pt` | 6,257,194 B | `635402c435786756c000694654271f1e6aee3eb039aa5e975bb8ec8e9ec0e34b` | NEU steel / six named steel classes |
| Concrete & Structural Cracks | Ultralytics YOLOv8 | `crack_detection.pt` | 22,522,595 B | `386155cae09bee6af1ce99608fc42a32cafd40a25362b80037b4fa54f6999719` | structural surfaces / `crack` |

Source URLs, revisions, thresholds, preprocessing, artifact integrity data, and quality weights live in `backend/models/model-manifest.json`.

## 🧭 Model selection history

`backend/detection/model-selection.json` records the candidate decisions instead of presenting the current three models as arbitrary choices.

| Candidate | Decision | Reason |
| --- | --- | --- |
| Bayes-PFL | **Selected general** | best fit among the checked broad anomaly-localization candidates; requires meaningful category context |
| NEU YOLOv8 | **Selected specialist** | compact steel detector with six checkpoint-native steel-defect classes |
| Concrete crack YOLOv8 | **Selected specialist** | compact detector for visible structural cracks |
| `factory-defect-guard-v6-mc` | **Rejected general** | local cross-domain checks showed unreliable coverage and class confusion; checkpoint remains registered but `exposed: false` |
| YOLO-World X | **Rejected candidate** | local candidate checks showed poor localization, oversized boxes, and false positives on clean images |
| AnomalyCLIP | **Rejected candidate** | local cross-domain checks mixed successful cases with misses, false positives, and overly broad anomaly regions |

Historical runtime material remains historical. The rejected legacy factory checkpoint is retained for reproducibility but a consistency check prevents it from becoming operator-visible again. The AnomalyCLIP adapter is retained as an experimental backend slot, but no currently exposed model uses it.

## 🏷️ Product / category context

Bayes-PFL uses product/category text as CLIP prompt context. The value is guidance for zero-shot localization, not a whitelist of classes on which the target object must have been trained.

Current guided choices include:

| Evidence level | Product/category examples |
| --- | --- |
| locally checked | Bottle, Capsule, Screw, Metal nut |
| additional upstream MVTec examples | Hazelnut, Pill, Toothbrush, Tile, Wood, Carpet |
| general-vs-specialist comparison | Steel surface, Concrete surface |
| generic UI option | Other objects |

Custom text is also allowed. `Cable` and `Zipper` are intentionally absent from the curated suggestions because local candidate checks were unacceptable, although they can still be entered manually for experimentation.

The server normalizes category input to lowercase, accepts `_` as a backwards-compatible space separator, and requires 2-40 characters, Latin letters/spaces/hyphens, and at most three words. Invalid guided context returns HTTP 422.

## 🖼️ Samples

The operator Samples page contains 14 attributed examples:

| Group | Samples | Suggested model |
| --- | --- | --- |
| MVTec AD | Bottle good / broken large; Capsule good / crack; Screw good / manipulated front; Metal nut good / bent | Bayes-PFL general |
| Steel Surface | good surface, inclusion, scratch | Steel Surface specialist |
| Concrete & Structural Cracks | transverse, longitudinal, and diagonal crack examples | Concrete specialist |

The eight Bayes-PFL examples are pinned to one MVTec AD mirror revision. The three steel and three concrete examples are pinned to a historical repository source revision with their dataset attribution retained.

The separate `backend/samples/demo/` directory contains twelve tracked VisA images used for demo/evidence validation. Those files satisfy the repository's `at least 10 demo images` requirement but are not the operator Samples catalog.

Important UI behavior:

- clicking a sample supplies that sample's product/category context;
- clicking a sample **does not change the selected model**;
- `Use suggested model` is the explicit action that switches to the sample's specialist/general recommendation;
- source labels describe dataset metadata and are never presented as model predictions.

This allows the same source to be inspected first with Bayes-PFL and then with a matching specialist without hiding the model choice.

## 🔄 Inspection flow

```text
JPEG/PNG bytes
-> content validation and OpenCV decode
-> selected model + optional guided product context
-> model-specific inference and geometry restoration
-> original-coordinate native detections
-> annotated image + quality score + verdict
-> SQLite metadata + original/annotated media
```

Ultralytics specialists use the shared square-letterbox path. Bayes-PFL owns its `518x518` stretch, CLIP normalization, anomaly-map postprocessing, and original-coordinate restoration.

The pinned Bayes-PFL source files stay byte-exact. Device-specific upstream allocation issues are adapted in memory so CPU, CUDA, indexed CUDA, and MPS tensors stay on the resolved device.

## 🔌 API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/models` | list selectable models, curated guided categories, and installed/default state |
| `GET` | `/api/samples` | list the attributed 14-item operator showcase |
| `GET` | `/api/samples/{id}/image` | serve one pinned showcase image by catalog ID |
| `POST` | `/api/inspect` | inspect and persist an image |
| `POST` | `/api/stream` | inspect one JPEG frame without persistence |
| `GET` | `/api/history` | list/filter inspections |
| `GET` | `/api/history/{id}` | read one inspection with image data URLs |
| `DELETE` | `/api/history/{id}` | delete one inspection and owned media |
| `POST` | `/api/history/clear` | clear inspection history and owned media |
| `GET` | `/api/export` | export filtered history as CSV |

Bayes-PFL example:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "modelId=bayespfl-general-v1" \
  -F "productName=Capsule" \
  -F "image=@path/to/capsule.png;type=image/png"
```

The complete request/response contract is in `docs/api-contract.md`.

## 🎯 Quality score and extras

The backend returns integer `qualityScore` from 0 to 100. Higher values mean better quality. It is an application heuristic based on defect class, confidence, count, and bbox area; it is not calibrated metrology or a safety measurement.

The project also includes:

- live frame inspection through `POST /api/stream`;
- backend-authoritative quality scoring;
- server-side filtered CSV export;
- original and annotated inspection media;
- model-aware history and type filters.

## 🧪 Tests and verification

Run the canonical repository checks from an activated environment:

```bash
python scripts/validate.py
```

Useful focused commands:

```bash
python scripts/validate_architecture.py
python -m pytest
npm --prefix frontend test
npm --prefix frontend run build
```

The two tests that fetch pinned showcase bytes are opt-in so ordinary validation remains offline-stable:

```bash
INSPECT_VISION_RUN_NETWORK_TESTS=1 python -m pytest tests/integration/api/test_inspection_api.py -k 'sample_image or verified_screw'
```

Real-model qualification is separate from static/unit checks:

```bash
python scripts/probe_models.py --device auto
```

Hardware-specific runs are also available:

```bash
python scripts/probe_models.py --device cuda
python scripts/probe_models.py --device mps
python scripts/probe_models.py --device cpu
```

Runtime evidence is tied to the source that actually executed. Detector-bound source changes do not rewrite an older runtime record to look current; a new production-path probe is required.

Repository navigation and ownership rules are in `AGENTS.md`. Current capability status is in `docs/project-status.json`, and requirement-to-check mapping is in `docs/verification.md`.

## 📁 Project structure

```text
inspect-vision/
├── backend/
│   ├── detection/       detector adapters, selection metadata, prompt validation
│   ├── models/          model manifest and ignored local model artifacts
│   ├── routes/          FastAPI boundaries and operator sample catalog
│   ├── samples/         local VisA demo/evidence corpus and provenance
│   └── storage/         SQLite and media lifecycle
├── frontend/
│   ├── src/             React routes, components, context, API client and styles
│   └── tests/           frontend checks
├── docs/                contracts, status and runtime evidence
├── scripts/             installation, validation and runtime probes
├── tests/               Python unit and integration tests
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
└── README_RU.md
```

## ⚠️ Notes

- Bayes-PFL is an anomaly localizer, not a semantic defect classifier.
- The specialists are intentionally narrow; their semantic advantage applies inside their trained domains.
- Model weights are ignored by Git and installed separately.
- The operator showcase image endpoints use pinned network sources; ordinary repository validation does not fetch them.
- Sample source labels are dataset metadata, not cached or fabricated model output.
- The default frontend path uses the real backend.
- Historical runtime evidence is not modified to claim execution by newer source.

## 🧑‍💻 Author

- Nazar Yestayev (@nyestaye)
