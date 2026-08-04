# Backend

The reusable detection library is implemented under `backend/detection`, with
detection-owned model loading and preprocessing utilities under `backend/utils`.
It has no FastAPI or persistence dependency.

`backend/main.py` composes FastAPI over the lazy multi-model detection manager
and SQLite/media storage service. Upload, model registry, live, history, and CSV
endpoints follow `docs/api-contract.md`. Runtime settings are validated by
`backend/config.py` from `INSPECT_VISION_*` variables.
