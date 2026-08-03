# Shared contracts

Stable cross-module DTO and schema projections belong here. The Pydantic HTTP
projection is implemented at `backend/models/record.py` and is explicitly owned
by this module in `module-map.json`. Shared contracts must not contain
application helpers, inference implementation, or persistence code.
