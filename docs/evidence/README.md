# Runtime evidence

Runtime-verification artifacts are stored by milestone. Documentation claims
alone are not evidence. Evidence must be reproducible, sanitized, and tied to a
source commit and command.

Completed runtime bundles are historical records. Their `sourceFiles` hashes
must resolve to content present in repository history, but ordinary later source
changes do not rewrite or invalidate the recorded measurements. The retained
AnomalyCLIP public-API bundle is likewise a historical compatibility milestone;
no currently exposed model uses the AnomalyCLIP backend.

Current model evidence is recorded under `models/` and remains bound to the
source commit named inside each artifact. Detector-bound source changes require a
fresh production-path probe before the evidence can be described as current.
The records include Python/package versions, model and sample SHA-256 values,
native classes, confidences, original dimensions, and bounded `xyxy` values.
Research-use qualification source images are downloaded to a temporary directory
and are not stored here.

Inspection-service evidence is under `inspection-service/`:

- `inspection-service-acceptance.json` records the selected production-service
  path, preprocessing and quality contracts, original-coordinate positive-area
  defects, source hashes, and annotated hashes for its recorded source snapshot.
- Three `*-annotated.png` outputs prove that annotation was emitted at the
  original image dimensions for that milestone. Their pinned source URLs and
  hashes are recorded in the JSON.

Main API and persistence evidence is under `api-persistence/`:

- `api-persistence-acceptance.json` records an actual loopback Uvicorn lifecycle
  using its explicitly recorded registered model and manifest confidence.
- The saved HTTP JSON covers POST inspect, list, detail, delete, and the empty
  list after deletion.
- The evidence records the pinned input URL/hash, byte-exact original hash,
  same-format annotated hash/dimensions, relative media paths, SQLite fields, and
  proof that no record or media file remains after delete.

API bonus evidence is under `api-bonuses/`:

- `api-bonuses-acceptance.json` records a real loopback Uvicorn stream request,
  proves identical history before/after it, and records a three-inspection
  filtered history/export sequence.
- `stream.json`, the two history snapshots, filtered history JSON, and filtered
  CSV are hash-bound artifacts. The CSV rows, order, and all four filters match
  the history projection exactly.
- Storage is cleared after the probe and the evidence records that all six media
  files were removed.

Historical AnomalyCLIP public API evidence is under `anomalyclip-public-api/`:

- `sample-contract.json` freezes exact remote files, hashes, dimensions,
  provenance, prior qualification observations, one valid zero-detection normal
  case, and the known non-gating cable limitation for that milestone.
- `public-api-acceptance.json` records the then-current four-model
  `/api/models` serialization, verified binary/calibration integrity, five real
  `/api/inspect` requests with matching history/detail records, and one real JPEG
  `/api/stream` request that left history unchanged.
- The bundle proves preservation through the production public path at its
  recorded source snapshot. It is not a claim that AnomalyCLIP is currently
  exposed, does not repeat accuracy qualification, and makes no accuracy claim.

Demo-dataset evidence is under `demo-samples/`:

- `demo-samples-acceptance.json` binds twelve tracked VisA images and four
  category annotation CSVs to hashes, dimensions, archive paths, and CC BY 4.0
  provenance.
- Source truth contains four normal and eight anomaly samples, four product
  categories, and ten distinct source defect labels. It is selected before any
  model call.
- The retained service run records the observations produced at its configured
  confidence. False positives on source-normal samples are retained exactly as
  observed; the run is not an accuracy benchmark and makes no accuracy claim.
- These same twelve files now back the operator `/api/samples` catalog locally.
  The API returns source truth and file metadata, not the retained
  `modelObservation` values as fresh predictions.
- Static validation does not require model weights; the runtime probe does.
