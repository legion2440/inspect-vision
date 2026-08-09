# Verification matrix

Statuses describe the repository state represented by committed implementation
and retained runtime records. `PASS` has a complete implementation/check path,
`PARTIAL` still has a documented limitation, and `PLANNED` has no implementation
claim.

| Requirement | Status | Implementation or plan | Check / record |
| --- | --- | --- | --- |
| Repository structure | PASS | Required frontend, FastAPI, detection, storage, model, shared-contract, test, and verification paths are present | `python scripts/validate_structure.py` |
| Comprehensive root README | PASS | Setup, model installation, platform-specific PyTorch setup, accelerator fallback, selection rationale, API, samples, structure, and validation are documented | `README.md` |
| Full application starts without errors | PARTIAL | Current repository validation and three-model production-service runtime qualification pass; full browser end-to-end startup remains outside the automated checks | `python scripts/validate.py`; `python scripts/probe_models.py --device auto` |
| Runtime device fallback | PASS | `auto` selects CUDA, then Apple MPS, then CPU; explicit `cpu`, `cuda`, `cuda:N`, and `mps` remain available and explicit unavailable accelerators fail clearly | device/config tests; `docs/env-model-contract.md` |
| Model registry and local paths | PASS | Manifest v3 keeps Bayes-PFL as default, exposes only Bayes-PFL plus two specialists, and retains the rejected legacy YOLO hidden for historical reproducibility | manifest/selection tests |
| Model selection decisions | PASS | Tracked selection metadata records selected/rejected registered models, external rejected candidates, cross-dataset protocol, curated prompts, and rejected prompts | `backend/detection/model-selection.json`; detection tests |
| Selectable models | PASS | `/api/models`, upload, live mode, dashboard, and samples share one explicit model selection; sample/category choices never auto-route to another model | API/frontend tests |
| Guided product context | PASS | Bayes-PFL category context is normalized, length/word/character validated, accepted by inspect/stream, and included in the runtime cache key | runtime/API/frontend tests |
| Bayes-PFL cross-dataset protocol | PASS | `train_visa.pth` is explicitly bound to VisA auxiliary training and MVTec AD held-out qualification; validation rejects an overlapping training/qualification domain | selection metadata/tests |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details are implemented | frontend build |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` implements drop and explicit file selection with client validation | frontend tests/build |
| Canvas bounding boxes | PASS | Viewer renders original pixels with a separate rescaled Canvas overlay | frontend implementation and retained browser observations |
| Defect list fields | PASS | Type, confidence, and coordinates are displayed | frontend implementation/build |
| History date/type filters | PASS | Frontend sends canonical filters and FastAPI applies combined SQLite filtering; type choices come from currently exposed model classes | API/storage/frontend tests |
| `POST /api/inspect` | PASS | Bounded multipart read, model/context selection, inference, persistence, and detail response are implemented | API integration tests |
| `POST /api/stream` | PASS | JPEG frames use the selected model/context through the same runtime manager without persistence | API/frontend tests |
| OpenCV/model preprocessing | PASS | Ultralytics uses shared letterbox profiles; Bayes-PFL owns 518x518 stretch and CLIP normalization | detection/runtime tests and manifest |
| History GET/DELETE/clear | PASS | List/detail/delete/clear use persisted metadata and owned media cleanup | API/storage tests |
| Required error messages | PASS | Unsupported content, upload limit, model lookup/install failure, guided-context validation, and inference failure map at the HTTP boundary | API integration tests |
| Real model inference | PASS | A fresh production-service probe qualified all three exposed models with `requestedDevice=auto` resolving to `cuda:0` on NVIDIA GeForce RTX 4080 Laptop GPU, PyTorch 2.12.1+cu126, and CUDA 12.6 | `docs/evidence/models/model-registry-acceptance.json` |
| Accurate boxes/types/confidence | PARTIAL | Native type preservation, finite confidence, positive bounded original-image boxes, and geometry ownership are enforced and observed in the current runtime record; benchmark accuracy is not claimed | core/service tests and current runtime evidence |
| Annotated backend image | PASS | DetectionService annotates original-size pixels; API stores and returns annotated plus original images separately | service/API persistence checks; current runtime evidence |
| Persisted timestamped records | PASS | SQLite metadata, relative media paths, detail hydration, deletion, and cleanup are implemented | storage/API tests |
| At least 10 demo images | PASS | Twelve attributed VisA source-truth demo images remain tracked separately from the operator showcase | demo validator and retained records |
| Operator showcase | PARTIAL | Eight MVTec AD good/bad entries cover bottle, capsule, screw, and metal nut; image bytes are proxied from a pinned remote mirror rather than redistributed in Git | `python scripts/validate_showcase_samples.py` |
| Model artifact installation | PASS | Model artifacts are pinned by source, size, and SHA-256; artifact download failures return manual placement and verification details | installer tests |
| Code quality and separation | PASS | API, detection, storage, frontend, and shared-contract boundaries plus repository-local checks are implemented | `python scripts/validate.py` |
| Quality-score bonus | PASS | Backend-authoritative 0-100 quality score is returned and persisted; UI labels higher values as better quality | service/API/frontend tests |
| CSV export bonus | PASS | Server export reuses canonical history filters and CSV projection | API/storage tests |

The tracked current runtime bundle was produced by the production-service probe
against source commit `5824fa1a647e1e05597f6750a2fd43e9d51e38aa`. It records
`auto` resolving to CUDA on an NVIDIA GeForce RTX 4080 Laptop GPU. Earlier
runtime bundles remain recoverable from Git history and stay bound to the source
snapshots they recorded. A future detector-source change must again set
`runtime-requalification-pending` until a new production-service probe is run.
