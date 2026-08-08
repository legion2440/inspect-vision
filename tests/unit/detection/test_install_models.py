from __future__ import annotations

import importlib.util
from pathlib import Path

from backend.utils.model_loader import ModelRegistry
from scripts.install_models import requested_models


_CASES_PATH = Path(__file__).with_name("install_models_cases.py")
_SPEC = importlib.util.spec_from_file_location("install_models_cases", _CASES_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("Could not load installer test cases")
_CASES = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CASES)

for _name in dir(_CASES):
    if _name.startswith("test_") and _name != "test_production_all_intentionally_includes_exposed_anomalyclip":
        globals()[_name] = getattr(_CASES, _name)


def test_production_all_matches_current_exposed_registry() -> None:
    selected = requested_models(ModelRegistry(), install_all=True)

    assert [model.model_id for model in selected] == [
        "bayespfl-general-v1",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
    ]
