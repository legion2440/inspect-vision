# Defect detection

This module owns model selection metadata, product/category validation, detector
lifecycles, preprocessing, inference, coordinate restoration, annotation, and
quality scoring.

`model-selection.json` records selected/rejected candidates, curated category
examples, and the Bayes cross-dataset protocol. Validation prevents a registered
model marked rejected there from being exposed to operators.

## Runtime context

`DetectionRuntimeManager` validates guided category input before loading a model.
For Bayes-PFL it lowercases input, treats `_` as a space separator, requires
2-40 characters using Latin letters/spaces/hyphens, and limits input to three
words. Services are cached by `(model ID, normalized category)`.

Device selection is portable. `auto` resolves in this order:

```text
CUDA -> Apple MPS -> CPU
```

Explicit `cpu`, `cuda`, `cuda:N`, and `mps` values remain available. Explicit
accelerators fail when unavailable instead of silently falling back; `auto` is
the normal cross-platform fallback mode. The platform-specific PyTorch wheel is
selected during installation, while `requirements-detection.txt` keeps only the
backend-neutral `torch==2.12.1` and `torchvision==0.27.1` version pins.

Ultralytics models use shared service-owned letterbox geometry. Bayes-PFL owns
its RGB conversion, bicubic `518x518` stretch, CLIP normalization, anomaly-map
postprocessing, and one restore to original-image coordinates.

## Bayes-PFL

`bayespfl-general-v1` intentionally uses:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification/showcase domain: MVTec AD
protocol: held-out cross-dataset zero-shot
```

Do not switch to `train_mvtec.pth` while MVTec AD remains the target
qualification domain. The current adapter keeps Gaussian sigma `8`, threshold
`0.72`, minimum component area ratio `0.0005`, and 25% bbox display padding.
These are application settings, not an upstream benchmark claim.

The native output is `anomaly`; the application does not invent semantic defect
subtypes. Meaningful product/category context matters, but curated examples are
suggestions rather than a target-class whitelist.

Pinned upstream Bayes files remain byte-exact. Device-allocation assumptions in
upstream transformer/PFL code are adapted only in memory so CPU, CUDA, indexed
CUDA, and MPS tensors remain on the selected device.

## Specialists

`neu-defect-yolov8` and `concrete-crack-yolov8` are separate independently
trained YOLOv8 checkpoints. Product/category selection never automatically
switches to either specialist, allowing explicit general-vs-specialist
comparison on the same input.

## Installation

Install the platform-specific PyTorch build first; see the root README for the
NVIDIA CUDA, CPU-only, and Apple Silicon/MPS commands. Then install model files:

```bash
python scripts/install_models.py --model bayespfl-general-v1
```

Artifacts are pinned by size and SHA-256. Bayes runtime source is fetched from a
pinned upstream revision and verified against exact Git blob IDs. If a model
artifact download fails, the installer prints manual source, destination,
expected size, SHA-256, and retry information.
