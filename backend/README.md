# Backend

The reusable detection library is implemented under `backend/detection`, with
detection-owned model loading and preprocessing utilities under `backend/utils`.
It has no FastAPI or persistence dependency.

The FastAPI application, inspection service, annotation, severity, and storage
remain planned. Their implementation must follow `docs/api-contract.md`,
`docs/env-model-contract.md`, and the boundaries in `ARCHITECTURE.md`.
