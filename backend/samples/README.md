# Samples

`model-probe-samples.json` pins three external NEU-DET images by source revision,
URL, and SHA-256 for local model verification. The probe downloads them into a
temporary directory; this repository does not redistribute the research-use
dataset files.

The inspection-service evidence stores three annotated derivative outputs under
`docs/evidence/inspection-service/`. Their exact source URLs, immutable source
hashes, output hashes, and dimensions are recorded in the adjacent acceptance
JSON; the unmodified source images remain temporary.

`demo/` contains twelve unmodified images from the Visual Anomaly (VisA)
industrial inspection dataset: four source-normal and eight source-anomaly
images across candle, capsules, cashew, and chewing gum. VisA data is released
under CC BY 4.0. Full annotation CSVs for those categories are preserved under
`provenance/` with source and tracked hashes.

`demo-samples.json` keeps `sourceGroundTruth` and `modelObservation` separate.
Source labels and defect cases are read from `image_anno.csv`; native model
classes, confidence, boxes, score, and status are observations at threshold
`0.25`, never ground truth. Model output does not influence sample selection.

Validate the static inventory with `scripts/validate_demo_samples.py`. Run all
all images through the selected production service at confidence `0.25` with
`scripts/probe_demo_samples.py`. `scripts/prepare_demo_samples.py` can rebuild
the source-quota inventory from the official archive; no synthetic image or fake
detection is used.

`showcase/` is a separate operator-facing collection of nine original source
images: three PCB images from DefectDet V1, three blade-surface images from the
GKN Blade Surface Defect Dataset V1, and three pavement/wall crack contexts from
HU Infrastructure Cracks V1. All three sources are pinned to a published
version under CC BY 4.0. `showcase-samples.json` records source paths, dataset
labels, attribution, hashes, dimensions, media types, and a recommended
registered model. It never stores model predictions.

The `/api/samples` metadata endpoint and `/api/samples/{id}/image` asset endpoint
serve this offline collection by manifest ID. Running one from the frontend
uses the operator's current model selection and the ordinary `/api/inspect`
path, so the result is persisted to history. Validate the catalog with
`scripts/validate_showcase_samples.py`.
