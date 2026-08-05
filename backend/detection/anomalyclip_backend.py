"""AnomalyCLIP anomaly-map backend with frozen postprocessing and scoring."""

from __future__ import annotations

import bisect
import hashlib
import itertools
import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from .base import DetectorBackend, GeometryOwnership
from .dto import Detection, InferenceResult
from .third_party.anomalyclip import AnomalyCLIP_PromptLearner, build_model


@dataclass(frozen=True, slots=True)
class FileIntegrity:
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class AnomalyClipBackendConfig:
    resize_width: int
    resize_height: int
    normalization_mean: tuple[float, float, float]
    normalization_std: tuple[float, float, float]
    features_list: tuple[int, ...]
    feature_map_layers: tuple[int, ...]
    dpam_layer: int
    prompt_length: int
    prompt_depth: int
    prompt_embedding_length: int
    gaussian_sigma: float
    map_threshold: float
    morphology_kernel: str
    morphology_kernel_size: int
    open_iterations: int
    close_iterations: int
    min_component_area_ratio: float
    merge_distance_px: int

    def __post_init__(self) -> None:
        if self.resize_width <= 0 or self.resize_height <= 0:
            raise ValueError("AnomalyCLIP resize dimensions must be positive")
        if self.resize_width != self.resize_height:
            raise ValueError("AnomalyCLIP runtime requires a square anomaly map")
        if len(self.normalization_mean) != 3 or len(self.normalization_std) != 3:
            raise ValueError("AnomalyCLIP normalization must contain three channels")
        if any(value <= 0.0 for value in self.normalization_std):
            raise ValueError("AnomalyCLIP normalization std values must be positive")
        if not self.features_list or not self.feature_map_layers:
            raise ValueError("AnomalyCLIP feature layers must not be empty")
        if any(index < 0 or index >= len(self.features_list) for index in self.feature_map_layers):
            raise ValueError("AnomalyCLIP feature-map layer index is out of range")
        if self.morphology_kernel not in {"ellipse", "rectangle", "none"}:
            raise ValueError("Unsupported AnomalyCLIP morphology kernel")
        if self.morphology_kernel_size <= 0 or self.morphology_kernel_size % 2 == 0:
            raise ValueError("AnomalyCLIP morphology kernel size must be positive and odd")
        if self.open_iterations < 0 or self.close_iterations < 0:
            raise ValueError("AnomalyCLIP morphology iterations must be non-negative")
        if not 0.0 <= self.map_threshold <= 1.0:
            raise ValueError("AnomalyCLIP map threshold must be between zero and one")
        if not 0.0 < self.min_component_area_ratio <= 1.0:
            raise ValueError("AnomalyCLIP minimum area ratio must be in (0, 1]")
        if self.merge_distance_px < 0 or self.gaussian_sigma < 0.0:
            raise ValueError("AnomalyCLIP merge distance and Gaussian sigma must be non-negative")


@dataclass(frozen=True, slots=True)
class _Component:
    label: int
    bbox: tuple[int, int, int, int]
    statistic: float


@dataclass(frozen=True, slots=True)
class _ComponentGroup:
    bbox: tuple[int, int, int, int]
    member_statistics: tuple[float, ...]


@dataclass(slots=True)
class _LoadedRuntime:
    torch: Any
    model: Any
    preprocess: Callable[[Image.Image], Any]
    text_features: Any


RuntimeLoader = Callable[["AnomalyClipBackend"], _LoadedRuntime]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as binary_file:
        for chunk in iter(lambda: binary_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_runtime_file(path: Path, integrity: FileIntegrity, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    if path.stat().st_size != integrity.size_bytes:
        raise ValueError(f"{label} size mismatch")
    actual_hash = _sha256(path)
    if actual_hash != integrity.sha256:
        raise ValueError(
            f"{label} hash mismatch: expected {integrity.sha256}, got {actual_hash}"
        )


def load_score_reference(path: Path, integrity: FileIntegrity) -> tuple[float, ...]:
    verify_runtime_file(path, integrity, "AnomalyCLIP score calibration")
    with path.open(encoding="utf-8") as calibration_file:
        payload = json.load(calibration_file)
    reference = payload.get("sortedReferenceComponentMeans")
    reference_count = payload.get("referenceCount")
    if (
        payload.get("schemaVersion") != 1
        or not isinstance(reference, list)
        or not reference
        or reference_count != len(reference)
    ):
        raise ValueError("Invalid AnomalyCLIP score calibration contract")
    normalized = tuple(float(value) for value in reference)
    if any(not math.isfinite(value) for value in normalized) or tuple(sorted(normalized)) != normalized:
        raise ValueError("AnomalyCLIP score calibration values must be finite and sorted")
    return normalized


def calibrated_component_score(statistic: float, reference: Sequence[float]) -> float:
    if not math.isfinite(statistic) or not reference:
        raise ValueError("Anomaly component score requires finite data and a clean reference")
    score = bisect.bisect_right(reference, statistic) / float(len(reference) + 1)
    return min(1.0, max(0.0, score))


def _morphology(binary: np.ndarray, config: AnomalyClipBackendConfig) -> np.ndarray:
    result = binary.astype(np.uint8)
    if config.morphology_kernel == "none":
        return result
    shape = (
        cv2.MORPH_ELLIPSE
        if config.morphology_kernel == "ellipse"
        else cv2.MORPH_RECT
    )
    kernel = cv2.getStructuringElement(
        shape,
        (config.morphology_kernel_size, config.morphology_kernel_size),
    )
    if config.open_iterations:
        result = cv2.morphologyEx(
            result,
            cv2.MORPH_OPEN,
            kernel,
            iterations=config.open_iterations,
        )
    if config.close_iterations:
        result = cv2.morphologyEx(
            result,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=config.close_iterations,
        )
    return result


def _bbox_distance(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> float:
    dx = max(left[0] - right[2], right[0] - left[2], 0)
    dy = max(left[1] - right[3], right[1] - left[3], 0)
    return math.hypot(dx, dy)


def _group_components(
    components: Sequence[_Component],
    merge_distance_px: int,
) -> tuple[_ComponentGroup, ...]:
    if not components:
        return ()
    parent = list(range(len(components)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right in itertools.combinations(range(len(components)), 2):
        if _bbox_distance(components[left].bbox, components[right].bbox) <= merge_distance_px:
            union(left, right)

    groups: dict[int, list[_Component]] = {}
    for index, component in enumerate(components):
        groups.setdefault(find(index), []).append(component)

    output = tuple(
        _ComponentGroup(
            bbox=(
                min(member.bbox[0] for member in members),
                min(member.bbox[1] for member in members),
                max(member.bbox[2] for member in members),
                max(member.bbox[3] for member in members),
            ),
            member_statistics=tuple(member.statistic for member in members),
        )
        for members in groups.values()
    )
    return tuple(sorted(output, key=lambda group: group.bbox))


def anomaly_components(
    anomaly_map: np.ndarray,
    config: AnomalyClipBackendConfig,
) -> tuple[_ComponentGroup, ...]:
    expected_shape = (config.resize_height, config.resize_width)
    if anomaly_map.shape != expected_shape:
        raise ValueError(f"Anomaly map has shape {anomaly_map.shape}, expected {expected_shape}")
    if not np.isfinite(anomaly_map).all():
        raise ValueError("Anomaly map contains non-finite values")
    binary = _morphology(anomaly_map >= config.map_threshold, config)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    min_area = config.min_component_area_ratio * float(
        config.resize_width * config.resize_height
    )
    retained: list[_Component] = []
    for label in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[label])
        statistic = float(anomaly_map[labels == label].mean())
        if area < min_area:
            continue
        retained.append(
            _Component(
                label=label,
                bbox=(x, y, x + width, y + height),
                statistic=statistic,
            )
        )
    return _group_components(retained, config.merge_distance_px)


def _load_backbone_archive(path: Path, torch_module: Any) -> Any:
    """Load only the verified TorchScript archive; there is no pickle fallback."""

    return torch_module.jit.load(str(path), map_location="cpu").eval()


def _load_prompt_checkpoint(path: Path, torch_module: Any) -> dict[str, Any]:
    checkpoint = torch_module.load(
        path,
        map_location="cpu",
        weights_only=True,
    )
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"prompt_learner"}:
        keys = sorted(checkpoint) if isinstance(checkpoint, dict) else []
        raise ValueError(f"Unexpected AnomalyCLIP prompt checkpoint keys: {keys}")
    return checkpoint


class AnomalyClipBackend(DetectorBackend):
    """Return generic anomaly components directly in original-image coordinates."""

    name = "anomalyclip"
    geometry_ownership = GeometryOwnership.BACKEND

    def __init__(
        self,
        *,
        model_id: str,
        backbone_path: Path,
        prompt_path: Path,
        calibration_path: Path,
        backbone_integrity: FileIntegrity,
        prompt_integrity: FileIntegrity,
        calibration_integrity: FileIntegrity,
        config: AnomalyClipBackendConfig,
        device: Any,
        expected_class_names: Sequence[str] = ("anomaly",),
        runtime_loader: RuntimeLoader | None = None,
    ) -> None:
        if tuple(expected_class_names) != ("anomaly",):
            raise ValueError("AnomalyCLIP nativeClasses must be exactly ['anomaly']")
        super().__init__(
            model_id=model_id,
            model_path=backbone_path,
            device=device,
            image_size=config.resize_width,
            confidence=config.map_threshold,
            iou=0.0,
            expected_class_names=expected_class_names,
        )
        self.backbone_path = Path(backbone_path)
        self.prompt_path = Path(prompt_path)
        self.calibration_path = Path(calibration_path)
        self.backbone_integrity = backbone_integrity
        self.prompt_integrity = prompt_integrity
        self.calibration_integrity = calibration_integrity
        self.config = config
        self._runtime_loader = runtime_loader
        self._runtime: _LoadedRuntime | None = None
        self._score_reference: tuple[float, ...] = ()

    @property
    def class_names(self) -> tuple[str, ...]:
        return ("anomaly",)

    @property
    def _torch_device(self) -> str:
        if self.device.kind == "cuda":
            return f"cuda:{self.device.torch_device}"
        return "cpu"

    def _load_default_runtime(self) -> _LoadedRuntime:
        import torch
        from torchvision.transforms import Compose, InterpolationMode, Normalize, Resize, ToTensor

        design_details = {
            "Prompt_length": self.config.prompt_length,
            "learnabel_text_embedding_depth": self.config.prompt_depth,
            "learnabel_text_embedding_length": self.config.prompt_embedding_length,
        }
        archive = _load_backbone_archive(self.backbone_path, torch)
        model = build_model(
            self.model_id,
            archive.state_dict(),
            design_details=design_details,
        )
        if self.device.kind == "cpu":
            model.float()
        prompt_learner = AnomalyCLIP_PromptLearner(model.to("cpu"), design_details)
        checkpoint = _load_prompt_checkpoint(self.prompt_path, torch)
        prompt_learner.load_state_dict(checkpoint["prompt_learner"], strict=True)
        prompt_learner.to(self._torch_device).eval()
        model.to(self._torch_device).eval()
        model.visual.DAPM_replace(DPAM_layer=self.config.dpam_layer)

        with torch.no_grad():
            prompts, tokenized_prompts, compound_prompts_text = prompt_learner(cls_id=None)
            text_features = model.encode_text_learn(
                prompts,
                tokenized_prompts,
                compound_prompts_text,
            ).float()
            text_features = torch.stack(torch.chunk(text_features, dim=0, chunks=2), dim=1)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        preprocess = Compose(
            [
                Resize(
                    (self.config.resize_height, self.config.resize_width),
                    interpolation=InterpolationMode.BICUBIC,
                ),
                lambda image: image.convert("RGB"),
                ToTensor(),
                Normalize(self.config.normalization_mean, self.config.normalization_std),
            ]
        )
        return _LoadedRuntime(torch, model, preprocess, text_features)

    def load(self) -> None:
        if self._runtime is not None:
            return
        verify_runtime_file(self.backbone_path, self.backbone_integrity, "CLIP backbone")
        verify_runtime_file(self.prompt_path, self.prompt_integrity, "AnomalyCLIP prompt checkpoint")
        self._score_reference = load_score_reference(
            self.calibration_path,
            self.calibration_integrity,
        )
        loader = self._runtime_loader or AnomalyClipBackend._load_default_runtime
        self._runtime = loader(self)

    @staticmethod
    def _similarity_map(torch_module: Any, patch_feature: Any, text_features: Any, size: int) -> Any:
        patch_feature = patch_feature / patch_feature.norm(dim=-1, keepdim=True)
        batch, image_tokens, channels = patch_feature.shape
        text_count = text_features.shape[0]
        similarity = (
            patch_feature.reshape(batch, image_tokens, 1, channels)
            * text_features.reshape(1, 1, text_count, channels)
        ).sum(-1)
        similarity = (similarity / 0.07).softmax(-1)
        similarity = similarity[:, 1:, :]
        side = int(similarity.shape[1] ** 0.5)
        if side * side != similarity.shape[1]:
            raise RuntimeError("AnomalyCLIP patch tokens do not form a square feature grid")
        mapped = similarity.reshape(batch, side, side, -1).permute(0, 3, 1, 2)
        mapped = torch_module.nn.functional.interpolate(mapped, size, mode="bilinear")
        return mapped.permute(0, 2, 3, 1)

    def _infer_map(self, frame: np.ndarray) -> np.ndarray:
        if self._runtime is None:
            raise RuntimeError("AnomalyCLIP backend is not loaded")
        runtime = self._runtime
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        tensor = runtime.preprocess(pil_image).reshape(
            1,
            3,
            self.config.resize_height,
            self.config.resize_width,
        ).to(self._torch_device)
        with runtime.torch.no_grad():
            _, patch_features = runtime.model.encode_image(
                tensor,
                self.config.features_list,
                DPAM_layer=self.config.dpam_layer,
            )
            maps = []
            for index, patch_feature in enumerate(patch_features):
                if index not in self.config.feature_map_layers:
                    continue
                similarity_map = self._similarity_map(
                    runtime.torch,
                    patch_feature,
                    runtime.text_features[0],
                    self.config.resize_width,
                )
                maps.append((similarity_map[..., 1] + 1 - similarity_map[..., 0]) / 2.0)
            if len(maps) != len(self.config.feature_map_layers):
                raise RuntimeError(
                    f"Expected {len(self.config.feature_map_layers)} anomaly maps, got {len(maps)}"
                )
            anomaly_map = runtime.torch.stack(maps).sum(dim=0)[0].detach().cpu().numpy()
        return np.asarray(
            gaussian_filter(anomaly_map, sigma=self.config.gaussian_sigma),
            dtype=np.float32,
        )

    def infer_batch(self, frames: Sequence[np.ndarray]) -> list[InferenceResult]:
        self.load()
        results: list[InferenceResult] = []
        for frame in frames:
            self.validate_frame(frame)
            image_height, image_width = frame.shape[:2]
            started = time.perf_counter()
            groups = anomaly_components(self._infer_map(frame), self.config)
            scale_x = image_width / float(self.config.resize_width)
            scale_y = image_height / float(self.config.resize_height)
            detections: list[Detection] = []
            for group in groups:
                x1, y1, x2, y2 = group.bbox
                original_box = (
                    max(0.0, min(float(image_width), x1 * scale_x)),
                    max(0.0, min(float(image_height), y1 * scale_y)),
                    max(0.0, min(float(image_width), x2 * scale_x)),
                    max(0.0, min(float(image_height), y2 * scale_y)),
                )
                if original_box[2] <= original_box[0] or original_box[3] <= original_box[1]:
                    continue
                score = max(
                    calibrated_component_score(value, self._score_reference)
                    for value in group.member_statistics
                )
                detections.append(
                    Detection(
                        class_id=0,
                        class_name="anomaly",
                        confidence=score,
                        xyxy=original_box,
                    )
                )
            results.append(
                InferenceResult(
                    detections=tuple(detections),
                    image_width=image_width,
                    image_height=image_height,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    backend=self.name,
                    device=self.device.name,
                    model_id=self.model_id,
                )
            )
        return results
