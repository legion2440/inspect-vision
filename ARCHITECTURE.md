# Architecture

## Status

The frontend application and its real-API boundary are implemented. Backend API,
OpenCV preprocessing, real model inference, persistence, demo datasets, and
runtime evidence are planned. See `docs/project-status.json` for the precise
baseline and limitations.

## System context

```mermaid
flowchart LR
    Operator["Operator"] --> Frontend["React inspection UI"]
    Frontend -->|"HTTP multipart and JSON"| API["FastAPI"]
    API --> Detection["OpenCV and defect model"]
    API --> History["Inspection history"]
    Detection --> Media["Original and annotated images"]
    History --> Database["SQLite metadata"]
```

## Components

### Frontend app

- Root: `frontend`.
- Owns routing, upload interaction, Canvas overlays, history UI, real/mock API
  selection, live frame capture, CSV download, and client-side severity fallback.
- Calls only interfaces defined in `docs/api-contract.md`.
- Implemented and build-verified.

### Backend API

- Root: `backend/routes` with application entrypoint `backend/main.py`.
- Will own HTTP validation, response serialization, CORS, error mapping, and route
  composition.
- Must not contain model inference or persistence implementation.
- Planned.

### Defect detection

- Root: `backend/detection`.
- Will own OpenCV preprocessing, model lifecycle, inference, coordinate mapping,
  annotation, and backend quality scoring.
- The model is loaded once and configured only through the environment/model
  contract.
- Planned.

### Inspection history

- Root: `backend/storage`.
- Will own SQLite metadata, media paths, filtering, deletion, clearing, and CSV
  projection.
- List responses omit image bodies; detail responses hydrate both image fields.
- Planned.

### Shared contracts

- Root: `shared`.
- Owns stable cross-module schemas and documented DTO semantics only.
- It must not depend on application, model, or persistence implementation.

### Audit evidence

- Root: `docs/evidence`.
- Owns reproducible command output and runtime artifacts mapped by
  `docs/audit-evidence.md`.
- Evidence is immutable per verified milestone and may not contain secrets, host
  paths, large model weights, or personal data.

## Boundary rules

- Frontend never imports backend Python or reads backend storage directly.
- API routes call detection and history through their public services.
- Detection never writes inspection records.
- History never loads or runs a model.
- Shared contracts depend on no higher-level module.
- Audit tooling may inspect public outputs but must not become a runtime dependency.

## Inspection sequence

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant CV as Detection
    participant DB as History
    UI->>API: POST /api/inspect image
    API->>CV: validated image bytes
    CV-->>API: defects, score, original, annotated
    API->>DB: persist metadata and media
    DB-->>API: inspection ID and timestamp
    API-->>UI: inspection detail contract
    UI->>UI: Canvas overlay on originalImageUrl
```

## Deferred decisions

The exact licensed manufacturing-defect model and dataset source remain open.
Their choice must be recorded with version, license, source, hash, classes, and
runtime evidence before AI integration is marked implemented.
