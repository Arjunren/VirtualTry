from __future__ import annotations

from threading import Event

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from virtual_tryon.config import GarmentCategory
from virtual_tryon.vton.base import GenerationCancelled, VTONEngine


class MockVTONEngine(VTONEngine):
    """Fast UI test double. Its output is deliberately labeled as non-AI."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._loaded = False

    @property
    def display_name(self) -> str:
        return "Mock preview (not AI)"

    def load(self) -> None:
        self._loaded = True

    def generate(
        self,
        person: Image.Image,
        garment: Image.Image,
        category: GarmentCategory,
        cancel_event: Event | None = None,
    ) -> Image.Image:
        if cancel_event and cancel_event.is_set():
            raise GenerationCancelled("Generation was cancelled.")
        canvas = ImageOps.fit(person.convert("RGB"), (self.width, self.height), Image.Resampling.LANCZOS)
        canvas = ImageEnhance.Brightness(canvas).enhance(0.72)
        thumb = ImageOps.contain(garment.convert("RGB"), (self.width // 3, self.height // 3))
        card = Image.new("RGB", (thumb.width + 20, thumb.height + 20), "white")
        card.paste(thumb, (10, 10))
        canvas.paste(card, (self.width - card.width - 18, self.height - card.height - 18))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width - 1, self.height - 1), outline="#7c5cff", width=5)
        draw.rectangle((0, 0, self.width, 52), fill="#16141f")
        draw.text((18, 17), f"MOCK PREVIEW · {category.value.upper()} · NOT AI OUTPUT", fill="white")
        return canvas
