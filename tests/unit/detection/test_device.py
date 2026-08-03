from __future__ import annotations

import pytest

from backend.detection.device import select_device


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


class TorchMock:
    def __init__(self, available: bool, count: int = 0) -> None:
        self.cuda = CudaMock(available, count)


def test_auto_uses_cpu_when_cuda_is_unavailable() -> None:
    device = select_device("auto", torch_module=TorchMock(False))

    assert device.kind == "cpu"
    assert device.torch_device == "cpu"


def test_auto_prefers_first_cuda_device() -> None:
    device = select_device("auto", torch_module=TorchMock(True, 2))

    assert device.kind == "cuda"
    assert device.torch_device == "0"
    assert device.name == "Test GPU 0"


def test_indexed_cuda_device_is_supported() -> None:
    device = select_device("cuda:1", torch_module=TorchMock(True, 2))

    assert device.torch_device == "1"
    assert device.name == "Test GPU 1"


def test_unavailable_cuda_index_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="index 2"):
        select_device("cuda:2", torch_module=TorchMock(True, 2))


def test_unsupported_device_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        select_device("mps", torch_module=TorchMock(False))
