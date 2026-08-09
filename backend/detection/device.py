"""Runtime device selection for CUDA, Apple MPS, and CPU fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    kind: str
    torch_device: str
    name: str
    backend: str


def _mps_backend(torch_module: Any) -> Any | None:
    backends = getattr(torch_module, "backends", None)
    return getattr(backends, "mps", None)


def _mps_available(torch_module: Any) -> bool:
    backend = _mps_backend(torch_module)
    check = getattr(backend, "is_available", None)
    return bool(check()) if callable(check) else False


def _mps_name(torch_module: Any) -> str:
    backend = _mps_backend(torch_module)
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        try:
            name = str(get_name()).strip()
            if name:
                return name
        except RuntimeError:
            pass
    return "Apple Metal GPU"


def select_device(
    force: str = "auto",
    *,
    torch_module: Any | None = None,
) -> DeviceInfo:
    if torch_module is None:
        import torch as torch_module

    requested = force.strip().lower()
    if (
        requested not in {"auto", "cpu", "cuda", "mps"}
        and not requested.startswith("cuda:")
    ):
        raise ValueError(f"Unsupported device: {force}")

    cuda_available = bool(torch_module.cuda.is_available())
    mps_available = _mps_available(torch_module)

    if requested == "cpu":
        return DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU")

    if requested == "mps":
        if not mps_available:
            raise RuntimeError("MPS was requested but is not available")
        return DeviceInfo("mps", "mps", _mps_name(torch_module), "PyTorch MPS")

    if requested == "auto" and not cuda_available:
        if mps_available:
            return DeviceInfo("mps", "mps", _mps_name(torch_module), "PyTorch MPS")
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
