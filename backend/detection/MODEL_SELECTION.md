# Model selection record

This document explains why the current operator registry contains Bayes-PFL plus
two specialists and why earlier broad candidates are not selectable. The
machine-readable counterpart is `backend/detection/model-selection.json`.
Historical runtime bundles remain separate immutable records of the source that
actually produced them.

## Selected models

### Bayes-PFL — selected general model

- checkpoint: `train_visa.pth`;
- auxiliary training domain: VisA;
- qualification/showcase domain: MVTec AD;
- protocol: held-out cross-dataset zero-shot;
- native output: `anomaly`;
- requires meaningful product/category context.

Local candidate checks produced useful localization on bottle, capsule, screw,
and metal-nut cases when the corresponding category context was supplied. A
manual prompt-sensitivity check also demonstrated the limitation clearly: the
same screw image produced the expected anomaly with `screw` context but could
silently return no detection with meaningless context. The UI therefore keeps a
visible category combobox rather than hiding a generic prompt.

### Steel Surface — selected specialist

`neu-defect-yolov8` is a separate YOLOv8 checkpoint with six native steel defect
classes. It stays manually selectable so a steel source can be compared against
Bayes-PFL without automatic routing.

### Concrete & Structural Cracks — selected specialist

`concrete-crack-yolov8` is a separate crack-detection checkpoint for concrete,
masonry, wall, and floor surfaces. It also remains manually selectable.

## Rejected broad candidates

### `factory-defect-guard-v6-mc`

Decision: rejected as the current general detector, retained only for historical
reproducibility.

Local broad-coverage checks missed required tile, screw, capsule, and metal-nut
cases and showed class confusion across the combined PCB/steel vocabulary. The
checkpoint is therefore still registered and hash-pinned, but its manifest entry
is `exposed: false`. Repository validation prevents a registered model marked
rejected from becoming operator-visible again.

### YOLO-World X

Decision: rejected candidate.

Local checks showed poor localization with oversized boxes and excessive false
positives. The retained experiment summary was:

- generic-normal checks: false positives on 5 / 5 cases;
- domain-vocabulary checks: false positives on 4 / 5 cases;
- localization quality was not acceptable for the general inspection role.

### AnomalyCLIP

Decision: rejected candidate.

Capsule and screw cases initially looked useful, but broader checks were not
stable enough for the general role. The local observations included:

- zipper: miss;
- metal nut, bottle, toothbrush, hazelnut, transistor, pill, and PCB cases:
  false-positive or overly broad anomaly regions in the checked examples.

Its historical public-API runtime bundle remains under `docs/evidence/` and is
validated as a historical source snapshot rather than rewritten to match the
current registry.

## Category preset policy

The Bayes category combobox is guidance, not a training-class whitelist.

| Group | Current presets |
| --- | --- |
| Locally checked | Bottle, Capsule, Screw, Metal nut |
| Additional upstream MVTec examples | Hazelnut, Pill, Toothbrush, Tile, Wood, Carpet |
| General-vs-specialist comparison | Steel surface, Concrete surface |
| Removed after local Bayes checks | Cable, Zipper |

Custom validated category input remains possible. Selecting a category never
changes the selected model automatically.

## Artifact independence

The three operator models are independently trained paths with different weight
files:

| Model | Main weights | Native purpose |
| --- | --- | --- |
| Bayes-PFL | `train_visa.pth` + `ViT-L-14-336px.pt` | cross-domain anomaly localization |
| Steel Surface | `defect_neu_yolov8.pt` | six-class steel defect detection |
| Concrete & Structural Cracks | `crack_detection.pt` | structural crack detection |

They are not one network with interchangeable modes. This is why operator model
selection remains explicit even when the product/category suggests a domain for
which a specialist exists.
