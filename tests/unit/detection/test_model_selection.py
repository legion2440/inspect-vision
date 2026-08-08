from __future__ import annotations

import copy
import json
from pathlib import Path

from backend.detection.model_selection import (
    MODEL_SELECTION_PATH,
    load_model_selection,
    validate_model_selection,
)
from backend.utils.model_loader import DEFAULT_MANIFEST_PATH


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_model_selection_contract_is_consistent() -> None:
    manifest = _load(DEFAULT_MANIFEST_PATH)
    selection = load_model_selection()

    assert validate_model_selection(manifest, selection) == []
    assert selection["bayesProtocol"] == {
        "checkpoint": "train_visa.pth",
        "auxiliaryTrainingDomain": "VisA",
        "qualificationDomain": "MVTec AD",
        "protocol": "held-out-cross-dataset-zero-shot",
        "note": "The VisA-trained checkpoint is intentionally qualified on MVTec AD categories outside its auxiliary training domain.",
    }


def test_rejected_registered_model_cannot_be_exposed() -> None:
    manifest = _load(DEFAULT_MANIFEST_PATH)
    selection = _load(MODEL_SELECTION_PATH)
    changed = copy.deepcopy(manifest)
    legacy = next(model for model in changed["models"] if model["id"] == "factory-defect-guard-v6-mc")
    legacy["exposed"] = True

    errors = validate_model_selection(changed, selection)

    assert "Rejected model cannot be exposed: factory-defect-guard-v6-mc" in errors


def test_bayes_training_and_qualification_domains_cannot_overlap() -> None:
    manifest = _load(DEFAULT_MANIFEST_PATH)
    selection = _load(MODEL_SELECTION_PATH)
    changed = copy.deepcopy(selection)
    changed["bayesProtocol"]["qualificationDomain"] = "VisA"

    errors = validate_model_selection(manifest, changed)

    assert "Bayes-PFL auxiliary training and qualification domains must be distinct" in errors


def test_locally_failed_prompts_are_not_curated_presets() -> None:
    selection = _load(MODEL_SELECTION_PATH)
    values = {item["value"] for item in selection["productNamePresets"]}

    assert "Cable" not in values
    assert "Zipper" not in values
    assert {"Bottle", "Capsule", "Screw", "Metal nut", "Steel surface", "Concrete surface"} <= values
