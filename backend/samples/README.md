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

`showcase-samples.json` defines a mixed operator catalog:

```text
Bayes-PFL
  Bottle       GOOD / BAD
  Capsule      GOOD / BAD
  Screw        GOOD / BAD
  Metal nut    GOOD / BAD

Steel Surface specialist
  3 attributed steel examples

Concrete & Structural Cracks specialist
  3 attributed crack examples
```

All eight Bayes examples are served from MMAD revision
`e88b7bd615ad582b0a7e8238066a9fb293a072b4`. The Screw GOOD entry is
`MVTec-AD/screw/test/good/001.png`, the exact source whose SHA-256 and byte
count match the previously checked `good-screw2.png`. The API verifies that
binding before serving it. MVTec AD attribution remains CC BY-NC-SA 4.0.

The steel and concrete examples restore the exact historical showcase bytes
through raw Git URLs pinned to commit
`f82fe4645ada00d5b01a16b9a05b2ea36795cce2`. Their original dataset
attribution remains tracked in the catalog, and the API verifies size/SHA-256
where those historical records provide them.

Each sample carries product/category context when Bayes-PFL needs one. Selecting
a sample may populate that category, but it never changes the operator's
selected model automatically. The explicit recommendation button is the only
sample action that changes the model.

Validate the current showcase catalog with:

```bash
python scripts/validate_showcase_samples.py
```

Historical sample provenance and evidence files remain immutable even when they
are no longer part of the current operator showcase.
