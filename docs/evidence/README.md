# Runtime evidence

Runtime-verification artifacts will be stored by milestone. Documentation claims
alone are not evidence. Evidence must be reproducible, sanitized, and tied to a
source commit and command.

Completed runtime bundles are historical records. Their `sourceFiles` hashes
must resolve to content present in repository history, but ordinary later source
changes do not rewrite or invalidate the recorded measurements. Current public
AnomalyCLIP compatibility is checked separately against its new source-bound
bundle.

Current model evidence:

- `models/ultralytics-model-probe.json` verifies both registered checkpoints
  directly through Ultralytics against the pinned three-image probe inventory.
- `models/detection-core-acceptance.json` verifies the same checkpoints and
  samples through the normalized detection core.

Both files record Python/package versions, model and sample SHA-256 values,
native classes, confidences, original dimensions, and bounded `xyxy` values.
The research-use source images are downloaded to a temporary directory and are
not stored here.

Inspection-service evidence is under `inspection-service/`:

- `inspection-service-acceptance.json` records the complete selected-model path
  at production confidence `0.25`, exact preprocessing and quality contracts,
  original-coordinate positive-area defects, source hashes, and annotated hashes.
- Three `*-annotated.png` outputs prove that annotation is emitted at the original
  image dimensions. Their pinned source URLs and hashes are recorded in the JSON.

Main API and persistence evidence is under `api-persistence/`:

- `api-persistence-acceptance.json` records an actual loopback Uvicorn lifecycle
  using its explicitly recorded registered model and manifest confidence.
- The saved HTTP JSON covers POST inspect, list, detail, delete, and the empty
  list after deletion.
- The evidence records the pinned input URL/hash, byte-exact original hash,
  same-format annotated hash/dimensions, relative media paths, SQLite fields, and
  proof that no record or media file remains after delete.
- Executed source-file SHA-256 values are authoritative until the final evidence
  commit updates the convenience `sourceCommit` pointer.

API bonus evidence is under `api-bonuses/`:

- `api-bonuses-acceptance.json` records a real loopback Uvicorn stream request,
  proves identical history before/after it, and records a three-inspection
  filtered history/export sequence.
- `stream.json`, the two history snapshots, filtered history JSON, and filtered
  CSV are hash-bound artifacts. The CSV rows, order, and all four filters match
  the history projection exactly.
- Storage is cleared after the probe and the evidence records that all six media
  files were removed.

AnomalyCLIP public API evidence is under `anomalyclip-public-api/`:

- `sample-contract.json` freezes exact remote files, hashes, dimensions,
  provenance, prior qualification observations, one valid zero-detection normal
  case, and the known non-gating cable limitation before the runtime run.
- `public-api-acceptance.json` records four-model `/api/models` serialization,
  verified binary/calibration integrity, five real `/api/inspect` requests with
  matching history/detail records, and one real JPEG `/api/stream` request that
  leaves history unchanged.
- The bundle proves preservation through the production public path. It does not
  repeat accuracy qualification, change the default, or make an accuracy claim.

Demo-dataset evidence is under `demo-samples/`:

- `demo-samples-acceptance.json` binds twelve tracked VisA images and four
  category annotation CSVs to hashes, dimensions, archive paths, and CC BY 4.0
  provenance.
- Source truth contains four normal and eight anomaly samples, four product
  categories, and ten distinct source defect labels. It is selected before any
  model call.
- The full service reproduced 65 observations at confidence `0.25`. All four
  source-normal samples produced false positives; they are retained exactly as
  observed. This run is not an accuracy benchmark and makes no accuracy claim.
- Static validation does not require model weights; the runtime probe does.
