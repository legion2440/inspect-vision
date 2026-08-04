# Detection models

`model-manifest.json` is the tracked source of truth for the local Ultralytics
weights used by Inspect-Vision. It records immutable source revisions, remote
filenames, MIT license metadata, SHA-256 values, input dimensions, and the
class names read from each checkpoint.

The `.pt` files remain local and are ignored by Git. A downloaded file is usable
only when its filename, byte size, and SHA-256 match the manifest.

Install the selected checkpoint from its pinned source revision:

```bash
.venv/Scripts/python.exe scripts/install_selected_model.py
```

The command leaves an already valid file untouched. New downloads are written
to a temporary file, verified against `sizeBytes` and `sha256`, and moved into
place only after both checks pass.

Run the equal real-model probe with the project environment:

```bash
.venv/Scripts/python.exe scripts/probe_models.py --engine core --device cpu --confidence 0.05
```

The selected model is `neu-defect-yolov8`. The broader 17-class checkpoint is
registered as an alternative, but its checkpoint class metadata differs from
its model card: it contains `capsule_defect`, not `cable_defect`. Inspect-Vision
uses the class names embedded in the checkpoint as authoritative runtime data.
