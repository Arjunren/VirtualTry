from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import ModuleType

from PIL import Image

from virtual_tryon.config import AppConfig, GarmentCategory, Precision
from virtual_tryon.vton.base import (
    CudaOutOfMemoryError,
    GenerationCancelled,
    ModelConfigurationError,
    VTONEngine,
)

LOGGER = logging.getLogger(__name__)
CATVTON_COMMIT = "999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e"


@contextmanager
def _offline_huggingface() -> object:
    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous


class CatVTONEngine(VTONEngine):
    """Adapter for the official CatVTON SD 1.5 pipeline.

    Upstream code/checkpoints are intentionally external because they use
    CC BY-NC-SA 4.0 and are not part of this MIT-licensed application.
    """

    def __init__(self, config: AppConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.repo_path = self._resolve(config.catvton_repo_path)
        self.checkpoint_path = self._resolve(config.catvton_checkpoint_path)
        self.base_model_path = self._resolve(config.catvton_base_model_path)
        self._pipeline: object | None = None
        self._automasker: object | None = None
        self._mask_processor: object | None = None
        self._torch: ModuleType | None = None
        self._device = "cpu"

    def _resolve(self, value: str) -> Path:
        candidate = Path(value).expanduser()
        return candidate if candidate.is_absolute() else self.project_root / candidate

    @property
    def display_name(self) -> str:
        return "CatVTON (local, non-commercial)"

    def _validate_installation(self) -> None:
        expected = {
            self.repo_path / "model" / "pipeline.py": "CatVTON source checkout",
            self.repo_path / "model" / "cloth_masker.py": "CatVTON automatic masker",
            self.checkpoint_path / "mix-48k-1024" / "attention": "CatVTON attention checkpoint",
            self.checkpoint_path / "DensePose": "DensePose checkpoint directory",
            self.checkpoint_path / "SCHP": "SCHP checkpoint directory",
            self.base_model_path / "model_index.json": "Stable Diffusion inpainting base model",
        }
        missing = [label for path, label in expected.items() if not path.exists()]
        if missing:
            raise ModelConfigurationError(
                "CatVTON is not installed completely: " + ", ".join(missing) + ". See README model setup."
            )
        try:
            commit = subprocess.run(
                ["git", "-C", str(self.repo_path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            dirty = subprocess.run(
                ["git", "-C", str(self.repo_path), "status", "--porcelain", "--untracked-files=no"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            raise ModelConfigurationError("The CatVTON source must be a verifiable Git checkout.") from error
        if commit != CATVTON_COMMIT or dirty:
            raise ModelConfigurationError(
                f"CatVTON source must be the clean pinned commit {CATVTON_COMMIT}."
            )

    def _select_precision(self, torch: ModuleType) -> object:
        requested = self.config.precision
        if self._device == "cpu":
            return torch.float32
        if requested == Precision.FP32.value:
            return torch.float32
        if requested == Precision.BF16.value:
            if not torch.cuda.is_bf16_supported():
                raise ModelConfigurationError("bf16 was selected but this GPU does not support it.")
            return torch.bfloat16
        if requested == Precision.FP16.value:
            return torch.float16
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    def load(self) -> None:
        if self._pipeline is not None:
            return
        self._validate_installation()
        try:
            import torch
            from diffusers.image_processor import VaeImageProcessor
        except ImportError as error:
            raise ModelConfigurationError(
                "CatVTON dependencies are not installed. See requirements-catvton.txt."
            ) from error

        if self.config.device == "cuda" and not torch.cuda.is_available():
            raise ModelConfigurationError("CUDA was selected but PyTorch cannot access a CUDA GPU.")
        self._device = "cuda" if self.config.device == "cuda" else (
            "cuda" if self.config.device == "auto" and torch.cuda.is_available() else "cpu"
        )
        dtype = self._select_precision(torch)

        repo_text = str(self.repo_path)
        if repo_text not in sys.path:
            sys.path.insert(0, repo_text)
        try:
            pipeline_module = importlib.import_module("model.pipeline")
            masker_module = importlib.import_module("model.cloth_masker")
            pipeline_file = Path(pipeline_module.__file__ or "").resolve()
            try:
                pipeline_file.relative_to(self.repo_path.resolve())
            except ValueError as error:
                raise ModelConfigurationError("A conflicting Python 'model' package was imported.") from error
            with _offline_huggingface():
                self._pipeline = pipeline_module.CatVTONPipeline(
                    base_ckpt=str(self.base_model_path),
                    attn_ckpt=str(self.checkpoint_path),
                    attn_ckpt_version="mix",
                    weight_dtype=dtype,
                    use_tf32=self._device == "cuda",
                    device=self._device,
                )
                self._automasker = masker_module.AutoMasker(
                    densepose_ckpt=str(self.checkpoint_path / "DensePose"),
                    schp_ckpt=str(self.checkpoint_path / "SCHP"),
                    device=self._device,
                )
            self._mask_processor = VaeImageProcessor(
                vae_scale_factor=8,
                do_normalize=False,
                do_binarize=True,
                do_convert_grayscale=True,
            )
            self._torch = torch
            LOGGER.info("model_loaded engine=catvton device=%s precision=%s", self._device, str(dtype))
        except Exception as error:
            self._pipeline = None
            raise ModelConfigurationError(f"CatVTON failed to load: {error}") from error

    def generate(
        self,
        person: Image.Image,
        garment: Image.Image,
        category: GarmentCategory,
        cancel_event: Event | None = None,
    ) -> Image.Image:
        if self._pipeline is None or self._automasker is None or self._mask_processor is None or self._torch is None:
            raise ModelConfigurationError("CatVTON has not been loaded.")
        if cancel_event and cancel_event.is_set():
            raise GenerationCancelled("Generation was cancelled.")

        try:
            generator = self._torch.Generator(device=self._device).manual_seed(42)
            mask = self._automasker(person.copy(), category.value)["mask"]
            if cancel_event and cancel_event.is_set():
                raise GenerationCancelled("Generation was cancelled.")
            mask = self._mask_processor.blur(mask, blur_factor=9)
            result = self._pipeline(
                image=person.copy(),
                condition_image=garment.copy(),
                mask=mask,
                num_inference_steps=self.config.inference_steps,
                guidance_scale=self.config.guidance_scale,
                width=self.config.output_width,
                height=self.config.output_height,
                generator=generator,
            )[0]
            if cancel_event and cancel_event.is_set():
                raise GenerationCancelled("Generation was cancelled.")
            return result.convert("RGB")
        except GenerationCancelled:
            raise
        except Exception as error:
            out_of_memory = getattr(self._torch, "OutOfMemoryError", ())
            cuda_oom = getattr(getattr(self._torch, "cuda", object()), "OutOfMemoryError", ())
            if (out_of_memory and isinstance(error, out_of_memory)) or (cuda_oom and isinstance(error, cuda_oom)):
                if self._device == "cuda":
                    self._torch.cuda.empty_cache()
                raise CudaOutOfMemoryError(
                    "The GPU ran out of memory. Select 384×512, close other GPU apps, and try again."
                ) from error
            raise
