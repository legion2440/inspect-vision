# Backend

The reusable detection library is implemented under `backend/detection`, with
detection-owned model loading and preprocessing utilities under `backend/utils`.
It has no FastAPI or persistence dependency.

`backend/main.py` composes FastAPI over `DetectionService` and the SQLite/media
storage service. Main upload and history endpoints follow
`docs/api-contract.md`; live frames and server CSV remain deferred. Runtime
settings are validated by `backend/config.py` from `INSPECT_VISION_*` variables.
