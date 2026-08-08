# Detection models

`model-manifest.json` v3 is the tracked source of truth for detector backends and
artifact integrity. `defaultModelId` identifies the initial operator model;
`exposed` controls the public operator registry. Selection decisions and the
Bayes cross-dataset protocol are tracked separately in
`backend/detection/model-selection.json` so a rejected checkpoint cannot drift
back into the UI unnoticed.

Model binaries remain local and are ignored by Git. An artifact is installed
only when filename, byte size, and SHA-256 match the manifest.

```bash
# default Bayes-PFL general model
.venv/Scripts/python.exe scripts/install_models.py

# one lightweight specialist
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# all currently exposed models
.venv/Scripts/python.exe scripts/install_models.py --all
```

The current operator registry contains exactly three independently trained model
paths:

- `bayespfl-general-v1`: default category-guided general anomaly localizer,
  native type `anomaly`, CLIP backbone plus `train_visa.pth`;
- `neu-defect-yolov8`: Steel Surface specialist with six native steel classes;
- `concrete-crack-yolov8`: Concrete & Structural Cracks specialist with native
  class `crack`.

`factory-defect-guard-v6-mc` remains registered only for historical
reproducibility. Local cross-domain checks rejected it as the general detector,
so its manifest entry is `exposed: false` and it must not appear through
`GET /api/models` or operator history filters.

## Bayes-PFL protocol

The deployment checkpoint is intentionally `train_visa.pth`:

```text
auxiliary training domain: VisA
qualification/showcase domain: MVTec AD
protocol: held-out cross-dataset zero-shot
```

The current MVTec operator examples are therefore outside the checkpoint's
auxiliary training domain. Do not replace this with `train_mvtec.pth` while
MVTec remains the qualification/showcase domain.

Bayes-PFL requires meaningful product/category context. The runtime normalizes
and validates it before constructing/caching a guided service. Curated examples
are suggestions rather than a target-class whitelist.

## Artifact footprints

- CLIP `ViT-L-14-336px.pt`: 934,088,680 bytes;
- Bayes-PFL `train_visa.pth`: 109,523,051 bytes;
- steel `defect_neu_yolov8.pt`: 6,257,194 bytes;
- concrete `crack_detection.pt`: 22,522,595 bytes.

The legacy factory checkpoint is retained but hidden. Exact SHA-256, source
revision, license scope, preprocessing, thresholds, and quality weights remain in
`model-manifest.json`.

Installed exposed models can be exercised through the production manager/service
path:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --device cpu
```

A probe result becomes current evidence only after that command actually runs on
the current detector-bound source. Prior bundles remain immutable historical
records.
