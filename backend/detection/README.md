# Defect detection

The module owns model integrity checks, device selection, Ultralytics loading,
native multiclass inference, inspection preprocessing, coordinate restoration,
annotation, and authoritative quality scoring. It has no HTTP, persistence,
tracking, video, or UI dependency.

Input contract:

- `numpy.ndarray`;
- `uint8` pixels;
- `H × W × 3` BGR layout;
- non-empty dimensions.

Core detections contain only `class_id`, `class_name`, `confidence`, and input
image `xyxy`. The adapter returns every class produced by the model; there is no
person-only or other class filter. It clamps boxes and drops boxes that collapse
to zero area.

`DetectionService` applies exactly one application-level geometry transform:

```text
original BGR
-> letterbox 640x640
-> grayscale
-> CLAHE(2.0, 8x8)
-> BGR three-channel
-> Ultralytics inference at 640x640
-> restore_boxes once
-> original-coordinate service defects
-> quality-v1 and original-size annotation
```

Ultralytics still performs its internal tensor conversion and normalization, but
the already-square 640 input needs no further geometric resize or padding. Its
adapter result is therefore in the 640-square service coordinate space, and only
the service restores those boxes to the original image.

The default service mapping is an explicit identity mapping for the selected
six-class model. The generic core supports both registered checkpoints, but the
17-class alternative requires a separate explicit service mapping.

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
