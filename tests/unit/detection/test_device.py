from __future__ import annotations

from pathlib import Path

import pytest

from backend.detection.device import select_device


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class CudaMock:
    def __init__(self, available: bool, count: int = 0) -> None:
        self._available = available
        self._count = count

    def is_available(self) -> bool:
        return self._available

    def device_count(self) -> int:
        return self._count

    def get_device_name(self, index: int) -> str:
        return f"Test GPU {index}"


class MpsMock:
    def __init__(self, available: bool) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "Test Apple GPU"


class BackendsMock:
    def __init__(self, mps_available: bool) -> None:
        self.mps = MpsMock(mps_available)


class TorchMock:
    def __init__(
        self,
        cuda_available: bool,
        count: int = 0,
        *,
        mps_available: bool = False,
    ) -> None:
        self.cuda = CudaMock(cuda_available, count)
        self.backends = BackendsMock(mps_available)


def test_auto_uses_cpu_when_no_accelerator_is_available() -> None:
    device = select_device("auto", torch_module=TorchMock(False))

    assert device.kind == "cpu"
    assert device.torch_device == "cpu"


def test_auto_prefers_mps_over_cpu_when_cuda_is_unavailable() -> None:
    device = select_device("auto", torch_module=TorchMock(False, mps_available=True))

    assert device.kind == "mps"
    assert device.torch_device == "mps"
    assert device.name == "Test Apple GPU"


def test_auto_prefers_first_cuda_device_over_mps() -> None:
    device = select_device(
        "auto",
        torch_module=TorchMock(True, 2, mps_available=True),
    )

    assert device.kind == "cuda"
    assert device.torch_device == "0"
    assert device.name == "Test GPU 0"


def test_explicit_mps_is_supported() -> None:
    device = select_device("mps", torch_module=TorchMock(False, mps_available=True))

    assert device.kind == "mps"
    assert device.backend == "PyTorch MPS"


def test_unavailable_mps_is_rejected_when_explicitly_requested() -> None:
    with pytest.raises(RuntimeError, match="MPS"):
        select_device("mps", torch_module=TorchMock(False))


def test_indexed_cuda_device_is_supported() -> None:
    device = select_device("cuda:1", torch_module=TorchMock(True, 2))

    assert device.torch_device == "1"
    assert device.name == "Test GPU 1"


def test_unavailable_cuda_index_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="index 2"):
        select_device("cuda:2", torch_module=TorchMock(True, 2))


def test_unsupported_device_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        select_device("gpu", torch_module=TorchMock(False))


def test_shared_requirements_do_not_force_cpu_only_pytorch() -> None:
    requirements = (REPOSITORY_ROOT / "requirements-detection.txt").read_text(encoding="utf-8")

    assert "torch==2.12.1\n" in requirements
    assert "torchvision==0.27.1\n" in requirements
    assert "+cpu" not in requirements
    assert "download.pytorch.org/whl/cpu" not in requirements
