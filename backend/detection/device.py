"""Runtime device selection for CPU and indexed CUDA devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    kind: str
    torch_device: str
    name: str
    backend: str


def select_device(
    force: str = "auto",
    *,
    torch_module: Any | None = None,
) -> DeviceInfo:
    if torch_module is None:
        import torch as torch_module

    requested = force.strip().lower()
    if requested not in {"auto", "cpu", "cuda"} and not requested.startswith("cuda:"):
        raise ValueError(f"Unsupported device: {force}")

    cuda_available = bool(torch_module.cuda.is_available())
    if requested == "cpu" or (requested == "auto" and not cuda_available):
        return DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU")

    if not cuda_available:
        raise RuntimeError("CUDA was requested but is not available")

    if requested in {"auto", "cuda"}:
        index = 0
    else:
        raw_index = requested.partition(":")[2]
        if not raw_index.isdigit():
            raise ValueError(f"Unsupported device: {force}")
        index = int(raw_index)

    device_count = int(torch_module.cuda.device_count())
    if index >= device_count:
        raise RuntimeError(
            f"CUDA device index {index} is unavailable; detected {device_count} device(s)"
        )
    name = str(torch_module.cuda.get_device_name(index))
    return DeviceInfo("cuda", str(index), name, "PyTorch CUDA")
