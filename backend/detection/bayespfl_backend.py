"""Bayes-PFL candidate backend for service-level model qualification."""

from __future__ import annotations

import gc
import hashlib
import importlib
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from .base import DetectorBackend, GeometryOwnership
from .dto import Detection, InferenceResult


BAYESPFL_SOURCE_COMMIT = "8f155a07e734913e021c33c469f16a1f75c60e5d"
OPENAI_CLIP_SHA256 = "3035c92b350959924f9f00213499208652fc7ea050643e8b385c2dac08641f02"
OPENAI_CLIP_SIZE_BYTES = 934_088_680


@dataclass(frozen=True, slots=True)
class BayesPflConfig:
    """Frozen upstream inference settings plus provisional bbox conversion."""

    image_size: int = 518
    features_list: tuple[int, ...] = (6, 12, 18, 24)
    num_flows: int = 10
    prompt_context_len: int = 5
    prompt_num: int = 3
    prompt_state_len: int = 5
    sample_num: int = 10
    seed: int = 333
    gaussian_sigma: float = 8.0
    map_threshold: float = 0.5
    min_component_area_ratio: float = 0.0005

    def __post_init__(self) -> None:
        if self.image_size <= 0:
            raise ValueError("Bayes-PFL image size must be positive")
        if not self.features_list or any(layer <= 0 for layer in self.features_list):
            raise ValueError("Bayes-PFL feature layers must be positive")
        if self.num_flows <= 0 or self.prompt_context_len <= 0:
            raise ValueError("Bayes-PFL flow and prompt lengths must be positive")
        if self.prompt_num <= 0 or self.prompt_state_len <= 0 or self.sample_num <= 0:
            raise ValueError("Bayes-PFL prompt/sample counts must be positive")
        if self.gaussian_sigma < 0.0:
            raise ValueError("Bayes-PFL Gaussian sigma must be non-negative")
        if not 0.0 <= self.map_threshold <= 1.0:
            raise ValueError("Bayes-PFL map threshold must be between zero and one")
        if not 0.0 < self.min_component_area_ratio <= 1.0:
            raise ValueError("Bayes-PFL minimum area ratio must be in (0, 1]")


@dataclass(slots=True)
class _BayesPflRuntime:
    torch: Any
    model_clip: Any
    model: Any
    text_encoder: Any
    tokenizer: Any
    preprocess: Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as binary_file:
        for chunk in iter(lambda: binary_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_openai_backbone(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"OpenAI CLIP backbone is missing: {path}")
    if path.stat().st_size != OPENAI_CLIP_SIZE_BYTES:
        raise ValueError("OpenAI CLIP backbone size mismatch")
    actual = sha256_file(path)
    if actual != OPENAI_CLIP_SHA256:
        raise ValueError(
            f"OpenAI CLIP backbone hash mismatch: expected {OPENAI_CLIP_SHA256}, got {actual}"
        )


def verify_source_checkout(source_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Bayes-PFL source checkout is missing: {source_dir}")
    try:
        completed = subprocess.run(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Bayes-PFL source directory must be a Git checkout") from error
    revision = completed.stdout.strip().lower()
    if revision != BAYESPFL_SOURCE_COMMIT:
        raise ValueError(
            "Bayes-PFL source revision mismatch: "
            f"expected {BAYESPFL_SOURCE_COMMIT}, got {revision or '<empty>'}"
        )


def _load_candidate_checkpoint(path: Path, torch_module: Any) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Bayes-PFL checkpoint is missing: {path}")
    checkpoint = torch_module.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"MyModel"}:
        keys = sorted(checkpoint) if isinstance(checkpoint, dict) else []
        raise ValueError(f"Unexpected Bayes-PFL checkpoint keys: {keys}")
    if not isinstance(checkpoint["MyModel"], dict):
        raise ValueError("Bayes-PFL MyModel state must be a dictionary")
    return checkpoint


def _component_boxes(
    anomaly_map: np.ndarray,
    *,
    threshold: float,
    min_area_ratio: float,
) -> tuple[tuple[tuple[int, int, int, int], float], ...]:
    if anomaly_map.ndim != 2 or not np.isfinite(anomaly_map).all():
        raise ValueError("Bayes-PFL anomaly map must be a finite HxW array")
    binary = np.asarray(anomaly_map >= threshold, dtype=np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    min_area = float(anomaly_map.shape[0] * anomaly_map.shape[1]) * min_area_ratio
    components: list[tuple[tuple[int, int, int, int], float]] = []
    for label in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[label])
        if area < min_area:
            continue
        score = float(np.mean(anomaly_map[labels == label]))
        components.append(((x, y, x + width, y + height), max(0.0, min(1.0, score))))
    return tuple(components)


class BayesPflBackend(DetectorBackend):
    """Run the official Bayes-PFL inference path behind DetectionService."""

    name = "bayespfl-candidate"
    geometry_ownership = GeometryOwnership.BACKEND

    def __init__(
        self,
        *,
        source_dir: Path,
        backbone_path: Path,
        checkpoint_path: Path,
        product_name: str,
        device: Any,
        config: BayesPflConfig | None = None,
        model_id: str = "bayespfl-general-candidate",
    ) -> None:
        active_config = config or BayesPflConfig()
        normalized_product = product_name.strip()
        if not normalized_product:
            raise ValueError("Bayes-PFL requires an explicit product/category name")
        super().__init__(
            model_id=model_id,
            model_path=checkpoint_path,
            device=device,
            image_size=active_config.image_size,
            confidence=active_config.map_threshold,
            iou=0.0,
            expected_class_names=("anomaly",),
        )
        self.source_dir = Path(source_dir).resolve()
        self.backbone_path = Path(backbone_path).resolve()
        self.checkpoint_path = Path(checkpoint_path).resolve()
        self.product_name = normalized_product
        self.config = active_config
        self._runtime: _BayesPflRuntime | None = None
        self.last_anomaly_map: np.ndarray | None = None

    @property
    def class_names(self) -> tuple[str, ...]:
        return ("anomaly",)

    @property
    def _torch_device(self) -> str:
        if self.device.kind == "cuda":
            return f"cuda:{self.device.torch_device}"
        return "cpu"

    def set_product_name(self, product_name: str) -> None:
        normalized = product_name.strip()
        if not normalized:
            raise ValueError("Bayes-PFL requires an explicit product/category name")
        self.product_name = normalized

    def _args(self) -> SimpleNamespace:
        return SimpleNamespace(
            vision_width=1024,
            text_width=768,
            embed_dim=768,
            features_list=list(self.config.features_list),
            num_flows=self.config.num_flows,
            prompt_context_len=self.config.prompt_context_len,
            prompt_num=self.config.prompt_num,
            prompt_state_len=self.config.prompt_state_len,
            sample_num=self.config.sample_num,
            image_size=self.config.image_size,
        )

    def _import_upstream(self) -> tuple[Any, Any]:
        source = str(self.source_dir)
        if source not in sys.path:
            sys.path.insert(0, source)
        previous_cwd = Path.cwd()
        try:
            # Upstream SimpleTokenizer resolves its BPE vocabulary from ./models.
            # Import from the pinned checkout root, then restore the caller cwd.
            os.chdir(self.source_dir)
            vp_module = importlib.import_module("models.VPB")
            clip_module = importlib.import_module("models.model_CLIP")
        finally:
            os.chdir(previous_cwd)
        for module in (vp_module, clip_module):
            module_path = Path(module.__file__).resolve()
            if self.source_dir not in module_path.parents:
                raise RuntimeError(f"Loaded Bayes-PFL module outside pinned checkout: {module_path}")
        return vp_module, clip_module

    def _seed_runtime(self, torch_module: Any) -> None:
        random.seed(self.config.seed)
        np.random.seed(self.config.seed)
        torch_module.manual_seed(self.config.seed)
        if torch_module.cuda.is_available():
            torch_module.cuda.manual_seed_all(self.config.seed)
        if hasattr(torch_module.backends, "cudnn"):
            torch_module.backends.cudnn.deterministic = True
            torch_module.backends.cudnn.benchmark = False

    def load(self) -> None:
        if self._runtime is not None:
            return
        verify_source_checkout(self.source_dir)
        verify_openai_backbone(self.backbone_path)

        import torch

        # Prove the pinned backbone is the expected TorchScript archive before the
        # upstream loader is allowed to touch it. This blocks its pickle fallback.
        archive = torch.jit.load(str(self.backbone_path), map_location="cpu").eval()
        del archive
        gc.collect()
        checkpoint = _load_candidate_checkpoint(self.checkpoint_path, torch)
        self._seed_runtime(torch)
        if self.device.kind == "cuda":
            torch.cuda.set_device(int(self.device.torch_device))

        vp_module, clip_module = self._import_upstream()
        args = self._args()
        model_clip, _, preprocess = clip_module.Load_CLIP(
            self.config.image_size,
            str(self.backbone_path),
            device=torch.device(self._torch_device),
        )
        model_clip.to(self._torch_device).eval()
        text_encoder = vp_module.TextEncoder(model_clip, args)
        model = vp_module.Context_Prompting(args=args).to(self._torch_device).eval()
        model.load_state_dict(checkpoint["MyModel"], strict=True)

        use_cuda = self.device.kind == "cuda"
        for flow_model in (model.PFL_context, model.PFL_normal, model.PFL_abnormal):
            flow_model.is_cuda = use_cuda

        self._runtime = _BayesPflRuntime(
            torch=torch,
            model_clip=model_clip,
            model=model,
            text_encoder=text_encoder,
            tokenizer=clip_module.tokenize,
            preprocess=preprocess,
        )

    def _anomaly_map(self, frame: np.ndarray) -> np.ndarray:
        if self._runtime is None:
            raise RuntimeError("Bayes-PFL backend is not loaded")
        runtime = self._runtime
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = runtime.preprocess(Image.fromarray(rgb)).unsqueeze(0).to(self._torch_device)
        sample_count = self.config.prompt_num * self.config.sample_num

        with runtime.torch.no_grad():
            image_features, _, patch_tokens = runtime.model_clip.encode_image(
                image,
                list(self.config.features_list),
            )
            text_embeddings, _ = runtime.model.forward_ensemble(
                runtime.text_encoder,
                image_features,
                patch_tokens,
                [self.product_name],
                runtime.torch.device(self._torch_device),
                runtime.tokenizer,
                mode="test",
            )
            _, anomaly_maps_list = runtime.model(
                text_embeddings,
                image_features,
                patch_tokens,
                stage=2,
                mode="test",
            )
            maps: list[np.ndarray] = []
            for layer_map in anomaly_maps_list:
                for index in range(sample_count):
                    pair = runtime.torch.stack(
                        [
                            layer_map[:, index, :, :],
                            layer_map[:, index + sample_count, :, :],
                        ],
                        dim=1,
                    )
                    probability = runtime.torch.softmax(pair, dim=1)[:, 1, :, :]
                    maps.append(probability.detach().cpu().numpy())
        if not maps:
            raise RuntimeError("Bayes-PFL returned no anomaly maps")
        anomaly_map = np.mean(maps, axis=0)[0]
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
            anomaly_map = self._anomaly_map(frame)
            expected_shape = (self.config.image_size, self.config.image_size)
            if anomaly_map.shape != expected_shape:
                raise RuntimeError(
                    f"Bayes-PFL anomaly map has shape {anomaly_map.shape}, expected {expected_shape}"
                )
            self.last_anomaly_map = anomaly_map.copy()
            components = _component_boxes(
                anomaly_map,
                threshold=self.config.map_threshold,
                min_area_ratio=self.config.min_component_area_ratio,
            )
            scale_x = image_width / float(self.config.image_size)
            scale_y = image_height / float(self.config.image_size)
            detections: list[Detection] = []
            for (x1, y1, x2, y2), score in components:
                box = (
                    max(0.0, min(float(image_width), x1 * scale_x)),
                    max(0.0, min(float(image_height), y1 * scale_y)),
                    max(0.0, min(float(image_width), x2 * scale_x)),
                    max(0.0, min(float(image_height), y2 * scale_y)),
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                detections.append(
                    Detection(
                        class_id=0,
                        class_name="anomaly",
                        confidence=score,
                        xyxy=box,
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
