from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any


class EngineKind(str, Enum):
    MOCK = "mock"
    CATVTON = "catvton"


class GarmentCategory(str, Enum):
    UPPER = "upper"
    LOWER = "lower"
    OVERALL = "overall"


class Precision(str, Enum):
    AUTO = "auto"
    FP16 = "fp16"
    BF16 = "bf16"
    FP32 = "fp32"


@dataclass(slots=True)
class AppConfig:
    engine: str = EngineKind.MOCK.value
    catvton_repo_path: str = "models/CatVTON"
    catvton_checkpoint_path: str = "models/checkpoints/CatVTON"
    catvton_base_model_path: str = "models/checkpoints/stable-diffusion-inpainting"
    output_width: int = 384
    output_height: int = 512
    inference_steps: int = 30
    guidance_scale: float = 2.5
    device: str = "auto"
    precision: str = Precision.AUTO.value
    automatic_generation: bool = False
    allow_remote_images: bool = True
    max_file_bytes: int = 20 * 1024 * 1024
    max_width: int = 8192
    max_height: int = 8192
    max_pixels: int = 40_000_000
    debug_logging: bool = False

    def validate(self) -> None:
        if self.engine not in {item.value for item in EngineKind}:
            raise ValueError("engine must be 'mock' or 'catvton'")
        if self.device not in {"auto", "cuda", "cpu"}:
            raise ValueError("device must be auto, cuda, or cpu")
        if self.precision not in {item.value for item in Precision}:
            raise ValueError("unsupported precision")
        if (self.output_width, self.output_height) not in {(384, 512), (768, 1024)}:
            raise ValueError("resolution must be 384x512 or 768x1024")
        if not 10 <= self.inference_steps <= 100:
            raise ValueError("inference_steps must be between 10 and 100")
        if not 0.0 <= self.guidance_scale <= 7.5:
            raise ValueError("guidance_scale must be between 0 and 7.5")
        if not 1 <= self.max_file_bytes <= 100 * 1024 * 1024:
            raise ValueError("max_file_bytes is outside the safe range")
        if not 1 <= self.max_width <= 16384 or not 1 <= self.max_height <= 16384:
            raise ValueError("image dimensions are outside the safe range")
        if not 1 <= self.max_pixels <= 100_000_000:
            raise ValueError("max_pixels is outside the safe range")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        allowed = {field.name for field in fields(cls)}
        value = cls(**{key: val for key, val in raw.items() if key in allowed})
        value.validate()
        return value

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("configuration root must be an object")
            return cls.from_dict(raw)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, path: Path) -> None:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temporary.replace(path)
