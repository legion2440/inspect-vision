# Detection models

`model-manifest.json` v3 is the tracked source of truth for detector backends.
It records product metadata, immutable artifacts, explicit license scope, byte
size, SHA-256, native classes, input size, backend-specific runtime settings,
and quality weights. `defaultModelId` identifies the initial operator model;
`exposed` controls public API selection.

Model binaries remain local and are ignored by Git. An artifact is installed
only when filename, byte size, and SHA-256 match the manifest.

```bash
# install the default Bayes-PFL general model
.venv/Scripts/python.exe scripts/install_models.py

# install one specialist
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# install all exposed models
.venv/Scripts/python.exe scripts/install_models.py --all
```

The default install verifies the OpenAI CLIP backbone, `train_visa.pth`, and the
minimal pinned Bayes-PFL inference source set. The source files are fetched from
the upstream revision recorded in the manifest/backend and verified against exact
Git blob IDs. No separate source checkout is required.

The exposed registry contains:

- `bayespfl-general-v1`: default category-guided general anomaly localizer,
  native type `anomaly`, 518×518 CLIP preprocessing, application threshold
  `0.72`, Gaussian sigma `8`, minimum component ratio `0.0005`, and 25% bbox
  display padding. Requests require `productName`;
- `factory-defect-guard-v6-mc`: legacy multiclass General Manufacturing YOLO
  coverage model, 17 native classes and standard-color preprocessing;
- `neu-defect-yolov8`: Steel Surface specialist, six native classes,
  steel-enhanced preprocessing and confidence `0.25`;
- `concrete-crack-yolov8`: Concrete & Structural Cracks specialist, native class
  `crack`, standard-color preprocessing and confidence `0.25`.

Bayes-PFL is broad in product-category coverage but does not classify semantic
defect subtypes. Its component score is not a class probability. Specialist
models remain preferred when the inspected material/domain is known. Structural
relationship defects are not presented as a guaranteed Bayes-PFL strength.

The legacy broad YOLO checkpoint contains `capsule_defect` even though its model
card names `cable_defect`; runtime `model.names` remains authoritative.

Installed models can be exercised through the production manager/service path:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --device cpu
```
