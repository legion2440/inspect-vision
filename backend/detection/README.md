# Defect detection

This module owns the validated model registry projection, lazy detector runtimes,
preprocessing, native inference, coordinate restoration, annotation, and
authoritative quality scoring. It has no HTTP, persistence, tracking, video, or
UI dependency.

Input is a non-empty `uint8 H x W x 3` BGR NumPy array. Core detections contain
only `class_id`, `class_name`, `confidence`, and input-image `xyxy`; boxes are
clamped and zero-area boxes are dropped.

`DetectionRuntimeManager` resolves the selected model, loads registered artifacts
only on first use, and caches successful `DetectionService` objects. For
category-guided models, the product/category string is part of the runtime cache
key so concurrent model contexts are never changed by mutation.

Ultralytics detectors use service-owned geometry:

```text
original BGR
-> one square letterbox
-> standard-color OR grayscale + CLAHE + BGR×3
-> registered Ultralytics detector
-> one restore to original coordinates
-> native class validation
-> quality score and original-size annotation
```

Anomaly-map detectors use backend-owned geometry:

```text
original BGR
-> backend-owned model preprocessing
-> anomaly map + model-specific postprocessing
-> anomaly components restored to original coordinates by the backend
-> shared native class validation, quality score, and annotation
```

The geometry capability prevents `DetectionService` from applying a second
letterbox or coordinate restore.

## Bayes-PFL general model

`bayespfl-general-v1` is the default cross-domain anomaly-localization model. It
uses the CVPR 2025 Bayes-PFL inference path with the `train_visa.pth` checkpoint
and the pinned OpenAI CLIP `ViT-L-14-336px.pt` backbone.

Bayes-PFL requires a concrete product/category name for every inference request.
The public API accepts it as multipart field `productName`; the frontend exposes
the same input whenever a selected model declares `requiresProductName=true`.
The value is used by the native Bayes-PFL prompt path rather than replaced with a
generic object label.

The preprocessing follows the upstream test path: RGB conversion, bicubic
`518×518` stretch resize, tensor conversion, and CLIP normalization. The anomaly
map is smoothed with Gaussian sigma `8`. Product postprocessing uses a fixed map
threshold `0.72`, connected components with minimum area ratio `0.0005`, and a
25% bbox display margin around each retained component. The fixed threshold and
bbox policy are application settings; the upstream benchmark does not publish a
single deployment threshold.

The native defect type is `anomaly`. Its confidence is the mean anomaly score of
the retained component, not a semantic class probability. Manual local checks
showed useful local anomaly localization across fasteners, capsules, and bottles,
while structural relationship defects can remain outside this model's strength.
Use a specialist model when the inspected domain has one.

## Runtime sources and installation

Bayes-PFL model artifacts and the minimal inference source set are installed with
one command:

```text
python scripts/install_models.py --model bayespfl-general-v1
```

No external repository clone is required. Model binaries are verified by pinned
size and SHA-256. The minimal source files are downloaded from the pinned
Bayes-PFL source revision and verified against exact Git blob object IDs before
use. They remain untracked under
`backend/detection/third_party/bayespfl/runtime/`; provenance is documented in
`backend/detection/third_party/bayespfl/NOTICE.md`.

The pinned upstream vision transformer contains one hard-coded CUDA allocation.
The loader keeps the downloaded source exact and applies a one-line in-memory
compatibility adaptation so that allocation uses the active tensor device. This
preserves the inference calculation while allowing the project's CPU PyTorch
build to run it.

There is no class mapping layer: service defect types remain model-native names
validated against the manifest. Quality weights are model-owned and fall back
only to the explicit neutral `1.0` declared by that model.

`backend/utils/preprocessing.py` and `backend/utils/model_loader.py` are owned by
this module even though the required repository layout places them outside the
`backend/detection` directory.
