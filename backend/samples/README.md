# Samples

`backend/samples/demo/` is the single operator/demo image corpus. It contains fourteen committed images: eight MVTec Bayes-PFL examples (Bottle, Capsule, Screw, Metal nut), three steel examples, and three concrete/crack examples.

`backend/routes/sample_catalog.py` supplies their IDs, labels, attribution, product context, and recommended models. `/api/samples` exposes the catalog and `/api/samples/{id}/image` serves those same local files. No second demo set or runtime network fetch is used.

These fourteen images directly satisfy the assignment requirement for at least ten demo images and include clean and defective examples.

Validate them with:

```bash
python scripts/validate_demo_samples.py
```

`model-probe-samples.json` is separate runtime-verification input metadata; it is not another operator/demo corpus.
