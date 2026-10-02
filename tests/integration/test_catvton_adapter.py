from __future__ import annotations

from PIL import Image

from virtual_tryon.config import AppConfig, GarmentCategory
from virtual_tryon.vton.catvton import CatVTONEngine


class FakeMasker:
    def __call__(self, person, category):
        return {"mask": Image.new("L", person.size, 255)}


class FakeMaskProcessor:
    def blur(self, mask, blur_factor):
        return mask


class FakePipeline:
    def __call__(self, **kwargs):
        return [Image.new("RGB", (kwargs["width"], kwargs["height"]), "green")]


class FakeGenerator:
    def manual_seed(self, seed):
        return self


class FakeTorch:
    class cuda:
        OutOfMemoryError = RuntimeError

        @staticmethod
        def empty_cache():
            return None

    OutOfMemoryError = MemoryError

    @staticmethod
    def Generator(device):
        return FakeGenerator()


def test_adapter_calls_real_pipeline_contract(tmp_path) -> None:
    engine = CatVTONEngine(AppConfig(engine="catvton"), tmp_path)
    engine._pipeline = FakePipeline()
    engine._automasker = FakeMasker()
    engine._mask_processor = FakeMaskProcessor()
    engine._torch = FakeTorch()
    engine._device = "cuda"
    result = engine.generate(
        Image.new("RGB", (80, 120)),
        Image.new("RGB", (40, 60)),
        GarmentCategory.UPPER,
    )
    assert result.size == (384, 512)
