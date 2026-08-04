# Defect detection

This module owns the validated model registry projection, lazy Ultralytics
runtime, preprocessing profiles, native multiclass inference, coordinate
restoration, annotation, and authoritative quality scoring. It has no HTTP,
persistence, tracking, video, or UI dependency.

Input is a non-empty `uint8 H x W x 3` BGR NumPy array. Core detections contain
only `class_id`, `class_name`, `confidence`, and input-image `xyxy`; boxes are
clamped and zero-area boxes are dropped.

`DetectionRuntimeManager` resolves an optional model ID, loads a registered
checkpoint only on first use, and caches successful `DetectionService` objects.
The service uses the model's manifest configuration:

```text
original BGR
-> one square letterbox
-> standard-color OR grayscale + CLAHE + BGR×3
-> registered Ultralytics detector
-> one restore to original coordinates
-> native class validation
-> per-model quality-v1 and original-size annotation
```

There is no class mapping layer: service defect types are the checkpoint-native
names validated against the manifest. Quality weights are model-owned and fall
back only to the explicit neutral `1.0` declared by that model.

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
