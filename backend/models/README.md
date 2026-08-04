# Detection models

`model-manifest.json` is the tracked source of truth for selectable Ultralytics
detectors. It records product metadata, immutable checkpoint provenance,
license, byte size, SHA-256, native classes, input size, inference thresholds,
preprocessing profile, and quality weights. `defaultModelId` identifies the
coverage-oriented starting model.

The `.pt` files remain local and are ignored by Git. A checkpoint is installed
only when filename, byte size, and SHA-256 match the manifest.

```bash
# install default General Manufacturing model
.venv/Scripts/python.exe scripts/install_models.py

# install one specialist
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# install the complete registry
.venv/Scripts/python.exe scripts/install_models.py --all
```

Downloads use pinned revisions and a temporary file followed by an atomic move.
An already verified checkpoint is left untouched.

The registry currently contains:

- `factory-defect-guard-v6-mc`: General Manufacturing default, 17 native classes,
  standard-color preprocessing, confidence 0.05;
- `neu-defect-yolov8`: Steel Surface specialist, six native classes,
  steel-enhanced preprocessing, confidence 0.25;
- `concrete-crack-yolov8`: Concrete & Structural Cracks specialist, native class
  `crack`, standard-color preprocessing, confidence 0.25.

The broad checkpoint contains `capsule_defect` even though its model card names
`cable_defect`; runtime `model.names` is authoritative. Its low threshold and
probe observations are recorded without claiming accuracy superiority.

Qualify all installed models through the production manager/service pipeline:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --device cpu
```
