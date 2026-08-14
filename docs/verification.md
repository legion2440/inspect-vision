# Verification matrix

Statuses describe committed implementation and retained runtime records. `PASS` has a complete implementation/check path; `PARTIAL` has a documented remaining limitation.

| Requirement | Status | Implementation / check |
| --- | --- | --- |
| Repository structure | PASS | Required frontend, FastAPI, detection, storage, model, shared-contract, tests and verification paths; `python scripts/validate_structure.py` |
| Comprehensive README | PASS | Setup, model installation, device behavior, model rationale, API, operator showcase, separate demo corpus and validation are documented |
| Full application starts without errors | PARTIAL | Current source still needs canonical post-correction validation and fresh production-service qualification; full browser E2E is outside automated checks |
| Runtime device fallback | PASS | `auto` selects CUDA -> MPS -> CPU; explicit devices remain available |
| Model registry | PASS | Bayes-PFL is default; only Bayes-PFL, steel and concrete are exposed; rejected legacy YOLO remains hidden |
| Model selection decisions | PASS | Selection/rejection metadata, cross-dataset protocol and curated prompts are tracked |
| Selectable models | PASS | Dashboard, Inspect, live stream and Samples share explicit model state; sample recommendations never auto-switch the model |
| Guided product context | PASS | Bayes-PFL context is normalized/validated; one heavy service is cached per model and context is applied under the per-model lock |
| Bayes-PFL cross-dataset protocol | PASS | `train_visa.pth`: VisA auxiliary training, MVTec AD held-out qualification |
| Required TanStack routes | PASS | Dashboard, inspect, history and details are implemented |
| Drag/drop and file selection | PASS | ImageUploader implements both with client validation |
| Canvas bounding boxes | PASS | Original image + separately rescaled Canvas overlay; no double drawing |
| Defect list fields | PASS | Type, confidence and coordinates are displayed |
| History filters | PASS | Date/type/text filters share backend/CSV semantics |
| `POST /api/inspect` | PASS | Bounded read, selected model/context, inference, persistence and detail response |
| `POST /api/stream` | PASS | Same runtime/context path without persistence |
| OpenCV/model preprocessing | PASS | Ultralytics shared letterbox profiles; Bayes-PFL owns its 518x518 CLIP path |
| History GET/DELETE/clear | PASS | Persisted metadata/media lifecycle implemented |
| Required error messages | PASS | Upload/model/context/history errors mapped at HTTP boundary |
| Real model inference | PARTIAL | Retained CUDA probe qualified all three exposed models at source `5824fa1a647e1e05597f6750a2fd43e9d51e38aa`; runtime source changed and requires a fresh probe |
| Boxes/types/confidence | PASS | Native types, finite confidence, positive bounded original-coordinate boxes and geometry ownership are enforced; no scientific benchmark claim is made |
| Annotated backend image | PASS | DetectionService annotates original-size pixels and API stores/returns original + annotated media |
| Persisted timestamped records | PASS | SQLite metadata, relative media paths, detail hydration, deletion and cleanup implemented |
| At least 10 demo images | PASS | The same fourteen local files shown on `/samples` are committed in `backend/samples/demo/`; the set includes clean and defective cases across Bayes, steel, and concrete examples | `python scripts/validate_demo_samples.py`; API/frontend tests |
| Operator Samples catalog | PASS | `/api/samples` exposes the intended 14-item catalog: 8 MVTec Bayes + 3 steel + 3 concrete. API/frontend tests assert its composition. VisA demo/evidence images are not returned by this endpoint |
| Model artifact installation | PASS | Model artifacts are pinned by source, size and SHA-256 with manual fallback instructions |
| Code quality/separation | PARTIAL | Module boundaries and validators are implemented; current restored sample/catalog source still needs canonical validation |
| Quality-score bonus | PASS | Backend-authoritative 0-100 quality score returned/persisted |
| CSV export bonus | PASS | Server export reuses canonical history filters |

The retained runtime bundle belongs to source commit `5824fa1a647e1e05597f6750a2fd43e9d51e38aa` and records CUDA on an NVIDIA GeForce RTX 4080 Laptop GPU. It remains historical until a fresh production-service probe qualifies the current detector-bound source.

