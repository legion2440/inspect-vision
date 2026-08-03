# Runtime evidence

Runtime-verification artifacts will be stored by milestone. Documentation claims
alone are not evidence. Evidence must be reproducible, sanitized, and tied to a
source commit and command.

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
