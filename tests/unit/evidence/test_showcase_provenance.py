from __future__ import annotations

import copy
import json

import scripts.validate_showcase_samples as showcase_validator


def _manifest_payload() -> dict[str, object]:
    with showcase_validator.MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def test_current_mvtec_showcase_provenance_is_valid() -> None:
    assert showcase_validator.validate_showcase_samples() == []


def test_unpinned_mvtec_revision_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    manifest["datasets"][0]["sourceRevision"] = "0" * 40
    manifest_path = tmp_path / "showcase-samples.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(showcase_validator, "MANIFEST_PATH", manifest_path)

    errors = showcase_validator.validate_showcase_samples()

    assert "MVTec AD showcase provenance is incomplete or changed" in errors


def test_sample_asset_must_match_pinned_source_path(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    manifest["samples"][0]["assetUrl"] = (
        "https://huggingface.co/datasets/jiang-cc/MMAD/resolve/"
        f"{showcase_validator.EXPECTED_REVISION}/MVTec-AD/bottle/test/broken_large/999.png"
    )
    manifest_path = tmp_path / "showcase-samples.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(showcase_validator, "MANIFEST_PATH", manifest_path)

    errors = showcase_validator.validate_showcase_samples()

    assert any("asset URL/source path mismatch" in error for error in errors)
