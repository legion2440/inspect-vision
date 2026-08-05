# AnomalyCLIP runtime notice

The files in this directory are a minimal runtime adaptation of AnomalyCLIP at
commit `3911738c0867544f545a076ad78f3f11d9ecbfdf`:

- upstream: https://github.com/zqhang/AnomalyCLIP
- upstream license: MIT (see `LICENSE` in this directory)
- OpenAI CLIP source license: MIT (see `OPENAI-CLIP-LICENSE`)
- adapted files: `AnomalyCLIP.py`, `build_model.py`, `prompt_ensemble.py`,
  `simple_tokenizer.py`, and `bpe_simple_vocab_16e6.txt.gz`

The adaptation removes training/evaluation utilities, the optional `thop`
dependency, the unsafe pickle fallback in the upstream checkpoint loader, and
package-global imports. Model artifacts are not included in this repository.

The AnomalyCLIP repository license covers its source code. No separately stated
license for the distributed CLIP backbone or prompt checkpoint was confirmed;
their status is recorded literally in the model manifest.
