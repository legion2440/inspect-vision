# Bayes-PFL runtime notice

Inspect Vision downloads the minimal Bayes-PFL inference source set on demand from the upstream repository at pinned commit `8f155a07e734913e021c33c469f16a1f75c60e5d`.

Upstream project: https://github.com/xiaozhen228/Bayes-PFL

Paper: *Bayesian Prompt Flow Learning for Zero-Shot Anomaly Detection*, CVPR 2025.

The upstream README states that the repository code and dataset are licensed under the MIT license. The selected upstream revision does not contain a standalone root `LICENSE` file, so this notice preserves the exact upstream licensing statement and source revision rather than inventing additional license text.

Downloaded runtime files are not committed. `scripts/install_models.py` verifies every source file against its pinned Git blob object before it can be used. Inspect Vision applies one runtime-only compatibility adaptation while importing the pinned source: a hard-coded CUDA attention accumulator is allocated on the active tensor device instead, allowing the same inference math to run with the project's CPU PyTorch build.
