from __future__ import annotations

import copy
import hashlib
import json

from scripts.validate_architecture import (
    REPOSITORY_ROOT,
    _observations_match,
    _source_hash_exists_in_history,
)


def test_runtime_source_hash_is_current_or_explicitly_historical() -> None:
    evidence_path = (
        REPOSITORY_ROOT / "docs/evidence/models/model-registry-acceptance.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    relative_path = "backend/models/model-manifest.json"
    recorded_hash = evidence["sourceFiles"][relative_path]
    current_hash = hashlib.sha256(
        (REPOSITORY_ROOT / relative_path).read_bytes()
    ).hexdigest()

    assert _source_hash_exists_in_history(relative_path, recorded_hash) is True
    if recorded_hash != current_hash:
        status = json.loads(
            (REPOSITORY_ROOT / "docs/project-status.json").read_text(encoding="utf-8")
        )
        limitation_ids = {
            item["id"] for item in status["known_limitations"] if isinstance(item, dict)
        }
        assert "runtime-requalification-pending" in limitation_ids


def test_qualification_observation_comparison_rejects_semantic_tampering() -> None:
    expected = [
        {
            "type": "anomaly",
            "confidence": 0.75,
            "xyxy": [1.0, 2.0, 10.0, 20.0],
        }
    ]
    assert _observations_match(copy.deepcopy(expected), expected) is True

    changed_confidence = copy.deepcopy(expected)
    changed_confidence[0]["confidence"] = 0.5
    assert _observations_match(changed_confidence, expected) is False

    changed_box = copy.deepcopy(expected)
    changed_box[0]["xyxy"][2] = 11.0
    assert _observations_match(changed_box, expected) is False
