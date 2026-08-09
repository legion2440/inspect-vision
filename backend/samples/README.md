# Samples

The repository keeps two sample roles separate: runtime qualification sources and
the tracked local demo corpus.

## Runtime qualification sources

`model-probe-samples.json` pins remote images by URL and SHA-256 for executable
model qualification. Bayes-PFL is explicitly recorded as:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification domain: MVTec AD
```

The probe downloads source bytes into a temporary directory and does not
redistribute them. These sources are verification inputs; they are not served by
the operator Samples page.

## Local demo corpus

`demo/` contains twelve unmodified VisA images across candle, capsules, cashew,
and chewing gum. `demo-samples.json` records their tracked source provenance,
source annotations, hashes, dimensions, media types, and the retained historical
`modelObservation` exercise.

The source labels in `sourceGroundTruth` are dataset truth. The retained
`modelObservation` block is historical evidence only and is not returned as a
prediction by `/api/samples`.

The same twelve files are the application's operator demo catalog. The API maps
the manifest entries to `/api/samples` metadata and serves each image from
`backend/samples/demo/` through `/api/samples/{id}/image`. No runtime network
request is needed to browse or load the Samples page.

Selecting a demo supplies its product/category context but never changes the
operator's selected model automatically. The explicit recommendation button is
the only sample action that changes the model, and inspection still uses the
ordinary `/api/inspect` path so results are persisted to normal history.

Validate the corpus with:

```bash
python scripts/validate_demo_samples.py
```

The demo corpus therefore satisfies both the repository's tracked demo-image
requirement and the operator-facing sample workflow without maintaining a second
showcase manifest or a second set of sample assets.
