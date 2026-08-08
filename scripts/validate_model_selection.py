"""Validate model-selection decisions against the registered model manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.detection.model_selection import load_model_selection, validate_model_selection


MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"


def main() -> int:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    errors = validate_model_selection(manifest, load_model_selection())
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[OK] Model-selection decisions and Bayes cross-dataset protocol are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
