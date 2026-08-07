# Defect detection

This module owns the validated model registry projection, lazy detector
runtimes, preprocessing, native inference, coordinate restoration, annotation,
and authoritative quality scoring. It has no HTTP, persistence, tracking,
video, or UI dependency.

Input is a non-empty `uint8 H x W x 3` BGR NumPy array. Core detections contain
only `class_id`, `class_name`, `confidence`, and input-image `xyxy`; boxes are
clamped and zero-area boxes are dropped.

`DetectionRuntimeManager` resolves an optional model ID, loads registered
artifacts only on first use, and caches successful `DetectionService` objects.
Ultralytics detectors retain the established service-owned geometry path:

```text
original BGR
-> one square letterbox
-> standard-color OR grayscale + CLAHE + BGR×3
-> registered Ultralytics detector
-> one restore to original coordinates
-> native class validation
-> per-model quality-v1 and original-size annotation
```

Anomaly-map detectors declare backend-owned geometry instead:

```text
original BGR
-> backend-owned model preprocessing
-> anomaly map + model-specific postprocessing
-> anomaly components restored to original coordinates by the backend
-> shared native class validation, quality-v1, and annotation
```

The ownership capability prevents `DetectionService` from applying a second
letterbox or coordinate restore. AnomalyCLIP is publicly selectable without
changing the coverage-oriented default. Its runtime qualification proves the
ordinary inspect/stream API integration and preserves the previously recorded
model observations; it does not upgrade the model's partial accuracy result.

There is no class mapping layer: service defect types are model-native names
validated against the manifest. AnomalyCLIP emits only `anomaly`, and its
confidence value is an empirical score relative to clean calibration
components—not a class probability. Quality weights are model-owned and fall
back only to the explicit neutral `1.0` declared by that model.

## Bayes-PFL candidate runner

`backend/detection/bayespfl_backend.py` and
`scripts/run_bayespfl_candidate.py` provide a service-level qualification path
for the upstream Bayes-PFL zero-shot anomaly model. The candidate is deliberately
not registered in `model-manifest.json`, `/api/models`, or the frontend until its
local checkpoint is measured, hash-pinned, and its behavior is accepted.

The runner verifies an external Bayes-PFL Git checkout at source revision
`8f155a07e734913e021c33c469f16a1f75c60e5d`, reuses the already pinned OpenAI
`ViT-L-14-336px.pt` backbone, and loads the local Bayes-PFL checkpoint with
`weights_only=True`. No upstream source tree or candidate checkpoint is copied
into this repository.

Bayes-PFL requires an explicit target product/category name at inference time;
its upstream prompt is built from that name. The candidate runner therefore
requires each image as `--case PRODUCT=IMAGE` instead of silently substituting a
generic product name.

The preprocessing follows the upstream test path: RGB conversion, bicubic
`518×518` resize, tensor conversion, and CLIP normalization. Geometry is owned by
the backend and restored to original coordinates exactly once. The upstream test
path also applies Gaussian smoothing with sigma `8` to the anomaly map.

Bayes-PFL does not publish a deployment bbox threshold. Its benchmark code
chooses a pixel threshold from target ground truth. For application-shaped local
inspection, the runner exposes a fixed `--threshold` (default `0.5`) and a small
connected-component area filter, then emits generic `anomaly` boxes through the
ordinary `DetectionService`. These bbox settings are candidate adapter settings,
not an upstream accuracy claim. The runner also writes the raw heatmap overlay so
model quality can be judged independently of the threshold.

Example:

```text
.venv/Scripts/python.exe scripts/run_bayespfl_candidate.py \
  --source-dir D:/TSchool/Bayes-PFL \
  --case capsule=D:/samples/capsule-crack.png \
  --case screw=D:/samples/screw-manipulated.png
```

Output goes to `.cache/bayespfl-candidate/`. `result.json` records the local
checkpoint size and SHA-256 together with the fixed candidate settings and per
image results.

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
