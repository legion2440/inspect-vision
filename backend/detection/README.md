# Defect detection

The detection core owns model integrity checks, device selection, Ultralytics
loading, inference, native class resolution, and normalized result DTOs. It has
no HTTP, persistence, tracking, video, or UI dependency.

Input contract:

- `numpy.ndarray`;
- `uint8` pixels;
- `H × W × 3` BGR layout;
- non-empty dimensions.

Output detections contain only `class_id`, `class_name`, `confidence`, and
original-image `xyxy`. The adapter returns every class produced by the model;
there is no person-only or other class filter.

For `.pt` inference, the original BGR array is passed to Ultralytics, which owns
its model-specific resize/letterbox and returns restored coordinates. The
utilities in `backend/utils/preprocessing.py` are independently tested for future
adapters and inspection-service work; they are not applied a second time to the
Ultralytics path.

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
