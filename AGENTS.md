# Repository instructions

This repository is organized around explicit feature boundaries. Work inside the
smallest owning module and update architecture metadata as part of any boundary
change.

## Environment

- The primary host is Windows 11.
- Use Git Bash for repository commands. Use PowerShell for Windows-specific work
  and WSL only when a Linux runtime is genuinely required.
- Repository text files use LF endings. Use repository-relative POSIX paths in
  metadata and documentation.

## Navigation order

1. Read `module-map.json`.
2. Find the module that owns the requested behavior.
3. Read the matching section in `ARCHITECTURE.md`.
4. Read the module entrypoint or public interface.
5. Read only its related configuration, implementation, tests, and evidence.
6. Cross a module boundary only through an edge allowed by
   `dependency-graph.json`.

`dependency-graph.json` is the editable source for dependency rules.
`docs/generated/dependency-graph.md` is generated and must not be edited by hand.

## Fixed modules

- `frontend-app`
- `backend-api`
- `defect-detection`
- `inspection-history`
- `shared-contracts`
- `verification-evidence`

Do not move detection logic into API routes, persistence into React, or backend
implementation details into shared contracts. The frontend communicates with
the backend only through the documented HTTP contract.

## File statuses

- `planned`: may be absent and must never be described as implemented.
- `implemented`: must exist and have an executable validation path.
- `generated`: must exist, name its generator and sources, and pass freshness
  validation.

Documentation is not runtime evidence. A feature is runtime-verified only when a
recorded command or evidence artifact proves the real path executed.

## Contract invariants

- `imageUrl` is the annotated backend image used for Download.
- `originalImageUrl` is the original image used by the Canvas viewer.
- Bounding boxes use original-image pixel coordinates with a top-left origin.
- History and CSV use the same inclusive `from`, `to`, `type`, and `q` filters.
- `qualityScore` is authoritative when returned by the backend; the browser score
  is only a UI fallback.
- Real API mode is the default. Mock inference must be explicitly enabled and
  must never hide a backend or model failure.
- Live detection processes at most one frame request at a time and uses actual
  video dimensions.
- Invalid type, oversize input, model failure, and missing record errors preserve
  the messages defined in `docs/api-contract.md`.
- The model directory and device belong in environment configuration. Registered
  checkpoint metadata, inference thresholds, preprocessing profiles, and quality
  weights belong in `backend/models/model-manifest.json`. Model weights, local
  databases, media, secrets, and `.env` files are never committed.
- Detection input is a non-empty `uint8 H x W x 3` BGR NumPy array. The reusable
  core returns every native model class as `class_id`, `class_name`, `confidence`,
  and input-image `xyxy`; it contains no class-specific filter.
- `DetectionRuntimeManager` resolves the optional request `modelId`, lazy-loads
  one `DetectionService` per registered model, and caches successful loads.
- Guided product/category context is applied to the cached detector under the
  per-model runtime lock immediately before inference; category changes must not
  load duplicate model services or leak context across concurrent requests.
- `DetectionService` is the production inspection boundary. It always owns native
  class validation, annotation, verdict, and the authoritative per-model
  `quality-v1` score. Geometry ownership is capability-driven: for
  `GeometryOwnership.SERVICE`, the service owns the manifest-selected preprocessing
  profile and one restore to original coordinates; for `GeometryOwnership.BACKEND`,
  the detector owns its preprocessing, model-specific postprocessing, and
  original-coordinate restoration, and the service must not transform its boxes
  again. Native class names are never semantically remapped.
- Changing the upload model aborts and invalidates the active request, clears its
  preview/result state, and prevents a late response from restoring stale data.
- Historical inspections remain readable after their model leaves the current
  registry; the persisted model ID is also the display-name fallback.
- Dashboard Quick Upload, Inspect, live stream, and Samples share one explicit
  model selection. A sample recommendation must never switch it automatically.
- Changing the Samples model aborts any pending source-image load before stale
  inference can start or navigate.
- `backend/samples/demo-samples.json` plus `backend/samples/demo/` are the single
  operator demo source. `sourceGroundTruth` is dataset truth, retained
  `modelObservation` is historical evidence only, and `/api/samples` never
  presents it as a fresh prediction. Demo images are served locally by manifest
  ID and inspection reuses the ordinary persisted `/api/inspect` path.
- Runtime qualification inputs remain separate from operator demos and may use
  pinned remote sources through verification scripts.
- `backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
  `defect-detection`, despite living outside that module's primary root.

## Change workflow

1. Change implementation and scoped tests together.
2. Update the owning documentation and API/env contracts when behavior changes.
3. Update `module-map.json` for path, status, interface, test, or artifact changes.
4. Update `dependency-graph.json` when dependencies change.
5. Regenerate architecture documentation.
6. Update `docs/verification.md` only with evidence that actually exists.
7. Update `docs/project-status.json` after a material milestone.
8. Run scoped checks, then `make validate`.

## Commands

```text
.venv/Scripts/python.exe scripts/validate.py
make validate
make validate-architecture
make validate-frontend
make test
make architecture
make check-architecture
make probe-service
make probe-api
make probe-bonuses
make validate-samples
make probe-samples
make status
.venv/Scripts/python.exe scripts/probe_inspection_service.py
.venv/Scripts/python.exe scripts/probe_api_persistence.py
.venv/Scripts/python.exe scripts/probe_api_bonuses.py
.venv/Scripts/python.exe scripts/validate_demo_samples.py
.venv/Scripts/python.exe scripts/probe_demo_samples.py
```

Detection model verification is implemented by `scripts/probe_models.py`; full
selected-model service evidence is generated by
`scripts/probe_inspection_service.py`; loopback HTTP and persistence evidence is
generated by `scripts/probe_api_persistence.py`. Main inspection/history API,
storage, dual-image encoding, non-persisted live inference, and server CSV are
implemented. Bonus runtime evidence is generated by
`scripts/probe_api_bonuses.py`. Demo images are an attributed, hash-bound,
unmodified VisA subset described by `backend/samples/demo-samples.json`.
Selection is based only on source annotation quotas. Keep `sourceGroundTruth`
from tracked CSVs separate from `modelObservation`; zero detections and false
positives must be recorded without relabeling source truth. The same tracked
demo corpus is served by the operator Samples page; there is no separate
showcase manifest or network-backed sample catalog.
GNU Make is optional on Windows;
`.venv/Scripts/python.exe scripts/validate.py` is the canonical Windows check.
