from __future__ import annotations

import copy
import json

from scripts.validate_showcase_samples import (
    MANIFEST_PATH,
    _defectdet_source_records,
    _hu_source_records,
    _validate_source_record,
)


def _manifest_samples() -> list[dict[str, object]]:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)["samples"]


def test_selected_labels_are_reconstructed_from_source_metadata() -> None:
    errors: list[str] = []
    defectdet_records = _defectdet_source_records(errors)
    hu_records = _hu_source_records(errors)

    assert errors == []
    for sample in _manifest_samples():
        assert _validate_source_record(sample, defectdet_records, hu_records) is None


def test_manifest_only_label_claim_is_rejected() -> None:
    errors: list[str] = []
    defectdet_records = _defectdet_source_records(errors)
    hu_records = _hu_source_records(errors)
    sample = copy.deepcopy(_manifest_samples()[0])
    sample["sourceLabels"] = ["missing pad"]

    mismatch = _validate_source_record(sample, defectdet_records, hu_records)

    assert errors == []
    assert mismatch is not None
    assert "sourceLabels differs from source metadata" in mismatch
