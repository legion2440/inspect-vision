# Samples

The repository has three different sample/evidence roles. They must not be
confused.

## Runtime qualification sources

`model-probe-samples.json` pins remote images by URL and SHA-256 for executable
model qualification. Bayes-PFL is explicitly recorded as:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification domain: MVTec AD
```

The probe downloads source bytes into a temporary directory and does not
redistribute them.

## Historical VisA demo corpus

`demo/` contains twelve unmodified VisA images across candle, capsules, cashew,
and chewing gum, with tracked provenance and source annotations. Its retained
`modelObservation` contract belongs to the historical steel-specialist demo
exercise; it is not current Bayes-PFL zero-shot evidence.

Validate that corpus with:

```bash
python scripts/validate_demo_samples.py
```

## Current operator showcase

`showcase-samples.json` now defines eight MVTec AD examples:

```text
Bottle      GOOD / BAD
Capsule     GOOD / BAD
Screw       GOOD / BAD
Metal nut   GOOD / BAD
```

The catalog pins MMAD mirror revision
`e88b7bd615ad582b0a7e8238066a9fb293a072b4` and records the MVTec AD
CC BY-NC-SA 4.0 attribution. The current operator showcase no longer contains
PCB entries.

To avoid silently creating another redistributed dataset snapshot in Git, the
showcase stores the pinned catalog and proxies image bytes from that exact mirror
revision through `/api/samples/{id}/image`. Network access is therefore required
when a showcase image is opened.

Each sample carries the correct Bayes product/category context. Selecting a
sample can populate that category, but it never changes the operator's currently
selected model automatically. This makes it possible to run the same image
through the general model and a specialist manually.

Validate the current showcase catalog with:

```bash
python scripts/validate_showcase_samples.py
```

Historical sample provenance and evidence files remain immutable even when they
are no longer part of the current operator showcase.
