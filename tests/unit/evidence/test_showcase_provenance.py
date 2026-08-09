from __future__ import annotations

import copy
import json

import scripts.validate_showcase_samples as showcase_validator


def _manifest_payload() -> dict[str, object]:
    with showcase_validator.MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def test_current_operator_showcase_provenance_is_valid() -> None:
    assert showcase_validator.validate_showcase_samples() == []


def test_unpinned_mvtec_revision_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    mvtec = next(dataset for dataset in manifest["datasets"] if dataset["id"] == "mvtec-ad")
    mvtec["sourceRevision"] = "0" * 40
    manifest_path = tmp_path / "showcase-samples.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(showcase_validator, "MANIFEST_PATH", manifest_path)

    errors = showcase_validator.validate_showcase_samples()

    assert "MVTec AD showcase provenance is incomplete or changed" in errors


def test_sample_asset_must_match_pinned_mvtec_source_path(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    manifest["samples"][0]["assetUrl"] = (
        "https://huggingface.co/datasets/jiang-cc/MMAD/resolve/"
        f"{showcase_validator.MVTEC_REVISION}/MVTec-AD/bottle/test/broken_large/999.png"
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


def test_verified_screw_good_binding_rejects_old_or_unverified_source(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    sample = next(item for item in manifest["samples"] if item["id"] == "mvtec-screw-good-001")
    sample["sourcePath"] = "MVTec-AD/screw/test/good/000.png"
    sample["assetUrl"] = (
        "https://huggingface.co/datasets/jiang-cc/MMAD/resolve/"
        f"{showcase_validator.MVTEC_REVISION}/MVTec-AD/screw/test/good/000.png"
    )
    manifest_path = tmp_path / "showcase-samples.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(showcase_validator, "MANIFEST_PATH", manifest_path)

    errors = showcase_validator.validate_showcase_samples()

    assert "Verified Screw good showcase binding is incomplete or changed" in errors
    assert "The rejected Screw good/000 showcase case must not return" in errors


def test_specialist_assets_must_remain_history_pinned(
    tmp_path,
    monkeypatch,
) -> None:
    manifest = copy.deepcopy(_manifest_payload())
    sample = next(item for item in manifest["samples"] if item["id"] == "steel-good-img4685")
    sample["assetUrl"] = "https://example.com/steel-good-img4685.jpg"
    manifest_path = tmp_path / "showcase-samples.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(showcase_validator, "MANIFEST_PATH", manifest_path)

    errors = showcase_validator.validate_showcase_samples()

    assert "Specialist showcase asset URL is not history-pinned: steel-good-img4685" in errors
