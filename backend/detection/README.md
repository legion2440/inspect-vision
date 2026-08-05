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
-> backend-owned 518×518 stretch + CLIP normalization
-> anomaly map + frozen postprocessing
-> calibrated anomaly components restored to original coordinates by the backend
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

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
