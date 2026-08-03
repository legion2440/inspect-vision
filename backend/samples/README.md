# Samples

`model-probe-samples.json` pins three external NEU-DET images by source revision,
URL, and SHA-256 for local model verification. The probe downloads them into a
temporary directory; this repository does not redistribute the research-use
dataset files.

The inspection-service evidence stores three annotated derivative outputs under
`docs/evidence/inspection-service/`. Their exact source URLs, immutable source
hashes, output hashes, and dimensions are recorded in the adjacent acceptance
JSON; the unmodified source images remain temporary.

`demo/` contains ten unmodified anomaly images from the Visual Anomaly (VisA)
industrial inspection dataset. VisA data is released under CC BY 4.0. Exact
source archive members, hashes, dimensions, anomaly provenance, attribution,
and selected-model native outputs are recorded in `demo-samples.json` and
`VISA-NOTICE.md`.

Validate the static inventory with `scripts/validate_demo_samples.py`. Run all
ten images through the selected production service at confidence `0.25` with
`scripts/probe_demo_samples.py`. `scripts/prepare_demo_samples.py` can rebuild
the inventory from the official archive; no synthetic image or fake detection is
used.
