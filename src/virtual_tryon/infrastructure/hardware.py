from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    device: str
    label: str
    supports_bf16: bool


def detect_hardware() -> HardwareInfo:
    try:
        import torch

        if torch.cuda.is_available():
            index = torch.cuda.current_device()
            name = torch.cuda.get_device_name(index)
            props = torch.cuda.get_device_properties(index)
            vram_gb = props.total_memory / (1024**3)
            supports_bf16 = bool(torch.cuda.is_bf16_supported())
            return HardwareInfo("cuda", f"{name} · {vram_gb:.1f} GB VRAM", supports_bf16)
    except (ImportError, RuntimeError):
        pass
    return HardwareInfo("cpu", "CPU · CatVTON will be very slow", False)
