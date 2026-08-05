from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from backend.detection.anomalyclip_backend import (
    AnomalyClipBackend,
    AnomalyClipBackendConfig,
    FileIntegrity,
    _load_backbone_archive,
    _load_prompt_checkpoint,
    anomaly_components,
    calibrated_component_score,
)
from backend.detection.device import DeviceInfo


def integrity(payload: bytes) -> FileIntegrity:
    return FileIntegrity(len(payload), hashlib.sha256(payload).hexdigest())


def config(*, size: int = 20) -> AnomalyClipBackendConfig:
    return AnomalyClipBackendConfig(
        resize_width=size,
        resize_height=size,
        normalization_mean=(0.48145466, 0.4578275, 0.40821073),
        normalization_std=(0.26862954, 0.26130258, 0.27577711),
        features_list=(6, 12, 18, 24),
        feature_map_layers=(0, 1, 2, 3),
        dpam_layer=20,
        prompt_length=12,
        prompt_depth=9,
        prompt_embedding_length=4,
        gaussian_sigma=4.0,
        map_threshold=0.1,
        morphology_kernel="ellipse",
        morphology_kernel_size=3,
        open_iterations=1,
        close_iterations=1,
        min_component_area_ratio=0.0025,
        merge_distance_px=1,
    )


def calibration_payload(reference: list[float]) -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": 1,
                "referenceCount": len(reference),
                "sortedReferenceComponentMeans": reference,
            },
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


class FixedMapBackend(AnomalyClipBackend):
    def __init__(self, anomaly_map: np.ndarray, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.anomaly_map = anomaly_map

    def _infer_map(self, frame: np.ndarray) -> np.ndarray:
        return self.anomaly_map.copy()


def backend_fixture(tmp_path: Path, anomaly_map: np.ndarray) -> FixedMapBackend:
    backbone_payload = b"torchscript"
    prompt_payload = b"prompt"
    score_payload = calibration_payload([0.1, 0.2, 0.3])
    backbone_path = tmp_path / "backbone.pt"
    prompt_path = tmp_path / "prompt.pth"
    calibration_path = tmp_path / "calibration.json"
    backbone_path.write_bytes(backbone_payload)
    prompt_path.write_bytes(prompt_payload)
    calibration_path.write_bytes(score_payload)
    return FixedMapBackend(
        anomaly_map,
        model_id="anomalyclip-general-v1",
        backbone_path=backbone_path,
        prompt_path=prompt_path,
        calibration_path=calibration_path,
        backbone_integrity=integrity(backbone_payload),
        prompt_integrity=integrity(prompt_payload),
        calibration_integrity=integrity(score_payload),
        config=config(size=anomaly_map.shape[0]),
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        runtime_loader=lambda _backend: object(),  # type: ignore[arg-type,return-value]
    )


def test_components_follow_frozen_threshold_morphology_and_merge() -> None:
    anomaly_map = np.zeros((20, 20), dtype=np.float32)
    anomaly_map[3:7, 2:6] = 0.4
    anomaly_map[3:7, 7:11] = 0.5

    groups = anomaly_components(anomaly_map, config())

    assert len(groups) == 1
    assert groups[0].bbox == (2, 3, 11, 7)
    assert groups[0].member_statistics == pytest.approx((0.4, 0.5))


def test_calibrated_component_score_is_bounded_and_not_raw_map_maximum() -> None:
    reference = (0.1, 0.2, 0.3)

    assert calibrated_component_score(-1.0, reference) == 0.0
    assert calibrated_component_score(0.2, reference) == 0.5
    assert calibrated_component_score(10.0, reference) == 0.75


def test_backend_rescales_components_once_to_original_coordinates(tmp_path: Path) -> None:
    anomaly_map = np.zeros((20, 20), dtype=np.float32)
    anomaly_map[4:10, 5:15] = 0.4
    backend = backend_fixture(tmp_path, anomaly_map)
    frame = np.zeros((100, 200, 3), dtype=np.uint8)

    result = backend.infer(frame)

    assert result.image_width == 200
    assert result.image_height == 100
    assert result.backend == "anomalyclip"
    assert result.detections[0].class_name == "anomaly"
    assert result.detections[0].confidence == 0.75
    assert result.detections[0].xyxy == pytest.approx((50.0, 20.0, 150.0, 50.0))


def test_prompt_loader_always_uses_weights_only() -> None:
    calls: list[dict[str, object]] = []

    class TorchSpy:
        @staticmethod
        def load(path: Path, **kwargs: object) -> dict[str, object]:
            calls.append({"path": path, **kwargs})
            return {"prompt_learner": {}}

    _load_prompt_checkpoint(Path("prompt.pth"), TorchSpy())

    assert calls == [
        {
            "path": Path("prompt.pth"),
            "map_location": "cpu",
            "weights_only": True,
        }
    ]


def test_backbone_loader_uses_torchscript_only() -> None:
    calls: list[tuple[str, str]] = []

    class Archive:
        def eval(self) -> "Archive":
            return self

    class JitSpy:
        @staticmethod
        def load(path: str, *, map_location: str) -> Archive:
            calls.append((path, map_location))
            return Archive()

    class TorchSpy:
        jit = JitSpy()

    archive = _load_backbone_archive(Path("backbone.pt"), TorchSpy())

    assert isinstance(archive, Archive)
    assert calls == [("backbone.pt", "cpu")]


def test_similarity_map_drops_cls_token_before_square_reshape() -> None:
    patch_features = torch.tensor(
        [[[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]]]
    )
    text_features = torch.tensor([[1.0, 0.0], [0.0, 1.0]])

    mapped = AnomalyClipBackend._similarity_map(
        torch,
        patch_features,
        text_features,
        8,
    )

    assert mapped.shape == (1, 8, 8, 2)


def test_integrity_failure_stops_before_runtime_loading(tmp_path: Path) -> None:
    anomaly_map = np.zeros((20, 20), dtype=np.float32)
    backend = backend_fixture(tmp_path, anomaly_map)
    backend.prompt_path.write_bytes(b"corrupt")

    with pytest.raises(ValueError, match="prompt checkpoint.*mismatch"):
        backend.load()


def test_tracked_production_calibration_has_qualified_hash_and_count() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "backend/models/config/anomalyclip-general-v1-score-calibration.json"
    )
    payload = path.read_bytes()
    calibration = json.loads(payload)

    assert len(payload) == 4107
    assert hashlib.sha256(payload).hexdigest() == (
        "0e7bff5d4316627f9ece3a2203efcf55233fef5f1eae652bcca3028ba81041e4"
    )
    assert calibration["referenceCount"] == 131
    assert len(calibration["sortedReferenceComponentMeans"]) == 131
