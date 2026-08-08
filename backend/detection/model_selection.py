"""Tracked model-selection decisions and guided-product presets."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODEL_SELECTION_PATH = REPOSITORY_ROOT / "backend/detection/model-selection.json"


@lru_cache(maxsize=1)
def load_model_selection(path: Path = MODEL_SELECTION_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as selection_file:
        value = json.load(selection_file)
    if not isinstance(value, dict):
        raise TypeError("Model selection metadata must contain a JSON object")
    return value


def product_name_presets() -> tuple[dict[str, str], ...]:
    presets = load_model_selection().get("productNamePresets", [])
    return tuple(
        {"value": str(item["value"]), "evidence": str(item["evidence"])}
        for item in presets
        if isinstance(item, dict)
    )


def validate_model_selection(manifest: dict[str, Any], selection: dict[str, Any] | None = None) -> list[str]:
    active = selection or load_model_selection()
    errors: list[str] = []
    if active.get("schemaVersion") != 1:
        errors.append("Model selection metadata must use schemaVersion 1")

    models = {
        model.get("id"): model
        for model in manifest.get("models", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    }
    decisions = active.get("registeredModels")
    if not isinstance(decisions, list):
        errors.append("Model selection metadata must contain registeredModels")
        decisions = []
    decision_by_id = {
        item.get("modelId"): item
        for item in decisions
        if isinstance(item, dict) and isinstance(item.get("modelId"), str)
    }
    if set(decision_by_id) != set(models):
        errors.append("Every registered model must have exactly one selection decision")

    for model_id, model in models.items():
        decision = decision_by_id.get(model_id, {})
        status = decision.get("status")
        if status not in {"selected", "rejected"}:
            errors.append(f"Model has invalid selection status: {model_id}")
            continue
        if status == "rejected" and model.get("exposed") is True:
            errors.append(f"Rejected model cannot be exposed: {model_id}")
        if status == "selected" and model.get("exposed") is not True:
            errors.append(f"Selected model must remain exposed: {model_id}")

    protocol = active.get("bayesProtocol", {})
    bayes = models.get(active.get("generalModelId"))
    if not isinstance(bayes, dict) or bayes.get("backend") != "bayespfl":
        errors.append("General model selection must reference the Bayes-PFL model")
    else:
        checkpoint = next(
            (
                artifact
                for artifact in bayes.get("artifacts", [])
                if artifact.get("id") == "bayes-checkpoint"
            ),
            {},
        )
        if checkpoint.get("source", {}).get("sourceFilename") != protocol.get("checkpoint"):
            errors.append("Bayes-PFL checkpoint differs from the documented cross-dataset protocol")
        training_domain = protocol.get("auxiliaryTrainingDomain")
        qualification_domain = protocol.get("qualificationDomain")
        if not training_domain or not qualification_domain or training_domain == qualification_domain:
            errors.append("Bayes-PFL auxiliary training and qualification domains must be distinct")
        if protocol.get("protocol") != "held-out-cross-dataset-zero-shot":
            errors.append("Bayes-PFL cross-dataset protocol metadata is missing")

    presets = active.get("productNamePresets")
    if not isinstance(presets, list) or len(presets) < 10:
        errors.append("Bayes-PFL must expose at least ten curated product/category presets")
        presets = []
    values = [item.get("value") for item in presets if isinstance(item, dict)]
    if len(values) != len(set(values)):
        errors.append("Product/category preset values must be unique")
    if {"Cable", "Zipper"} & set(values):
        errors.append("Locally rejected Cable/Zipper prompts must not return to curated presets")
    evidence_values = {item.get("evidence") for item in presets if isinstance(item, dict)}
    if not evidence_values <= {"local", "upstream", "comparison"}:
        errors.append("Product/category preset evidence labels are invalid")
    return errors
