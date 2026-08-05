# Detection models

`model-manifest.json` v3 is the tracked source of truth for detector backends.
It records product metadata, one or more immutable artifacts, literal license
scope, byte size, SHA-256, native classes, input size, backend-specific runtime
configuration, and quality weights. `defaultModelId` identifies the
coverage-oriented starting model; `exposed` controls public API selection.

The `.pt` and `.pth` files remain local and are ignored by Git. An artifact is
installed only when filename, byte size, and SHA-256 match the manifest.

```bash
# install default General Manufacturing model
.venv/Scripts/python.exe scripts/install_models.py

# install one specialist
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# install all exposed models
.venv/Scripts/python.exe scripts/install_models.py --all

# install AnomalyCLIP and both of its artifacts
.venv/Scripts/python.exe scripts/install_models.py --model anomalyclip-general-v1
```

Downloads use pinned revisions and a temporary file followed by an atomic move.
An already verified artifact is left untouched. `--all` means every exposed
model, so it now intentionally includes both AnomalyCLIP artifacts. A hidden
fixture remains covered to prevent future candidates entering `--all` before
exposure.

The registry currently contains:

- `factory-defect-guard-v6-mc`: General Manufacturing default, 17 native classes,
  standard-color preprocessing, confidence 0.05;
- `neu-defect-yolov8`: Steel Surface specialist, six native classes,
  steel-enhanced preprocessing, confidence 0.25;
- `concrete-crack-yolov8`: Concrete & Structural Cracks specialist, native class
  `crack`, standard-color preprocessing, confidence 0.25;
- `anomalyclip-general-v1`: public broad anomaly-localization model with two
  artifacts, fixed 518×518 stretch preprocessing, native class `anomaly`, and
  calibrated component scores. It provides no subtype classification;
  specialists remain preferred for known domains.

The current broad checkpoint contains `capsule_defect` even though its model
card names `cable_defect`; runtime `model.names` is authoritative. Its low
threshold and probe observations are recorded without claiming accuracy
superiority.

Qualify installed public models through the production manager/service pipeline:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --device cpu
```
