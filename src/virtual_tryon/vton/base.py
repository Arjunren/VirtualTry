from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Event

from PIL import Image

from virtual_tryon.config import GarmentCategory


class VTONError(RuntimeError):
    pass


class ModelConfigurationError(VTONError):
    pass


class GenerationCancelled(VTONError):
    pass


class CudaOutOfMemoryError(VTONError):
    pass


class VTONEngine(ABC):
    @abstractmethod
    def load(self) -> None:
        """Load model resources exactly once."""

    @abstractmethod
    def generate(
        self,
        person: Image.Image,
        garment: Image.Image,
        category: GarmentCategory,
        cancel_event: Event | None = None,
    ) -> Image.Image:
        """Generate a virtual try-on image without mutating its inputs."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...
