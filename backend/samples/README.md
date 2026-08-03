# Samples

`model-probe-samples.json` pins three external NEU-DET images by source revision,
URL, and SHA-256 for local model verification. The probe downloads them into a
temporary directory; this repository does not redistribute the research-use
dataset files.

The inspection-service milestone stores three annotated derivative outputs under
`docs/evidence/inspection-service/`. Their exact source URLs, immutable source
hashes, output hashes, and dimensions are recorded in the adjacent acceptance
JSON; the unmodified source images remain temporary.

This probe inventory does not satisfy the final demo-data requirement. A later
milestone must add at least ten redistributable manufacturing images covering
clean parts and multiple defect classes, with source, license, hash, dimensions,
and expected labels recorded for every sample.
