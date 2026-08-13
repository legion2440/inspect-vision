# Samples

The repository keeps three sample roles separate.

## Operator showcase

`backend/routes/sample_catalog.py` defines the Samples page catalog. It contains 14 operator-facing examples: eight MVTec cases for Bayes-PFL (Bottle, Capsule, Screw, Metal nut good/bad pairs), three steel examples, and three concrete/crack examples.

`GET /api/samples` exposes only this catalog. `GET /api/samples/{id}/image` resolves a known ID to its pinned source. A sample can supply product/category context, but it never changes the selected model automatically; inspection reuses the ordinary `/api/inspect` path.

## Local VisA demo/evidence corpus

`demo/` contains twelve tracked VisA images across candle, capsules, cashew and chewing gum. `demo-samples.json` records provenance, source annotations, hashes, dimensions and historical model observations. This corpus satisfies the repository demo-image requirement and supports evidence checks, but it is not the operator Samples page.

Validate it with:

```bash
python scripts/validate_demo_samples.py
```

## Runtime qualification sources

`model-probe-samples.json` pins separate sources for executable model qualification. Runtime evidence is tied to the source commit that actually executed and is not interchangeable with either the operator showcase or the local VisA demo corpus.
