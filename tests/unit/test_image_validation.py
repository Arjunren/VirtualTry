from __future__ import annotations

import io

import pytest
from PIL import Image

from virtual_tryon.imaging.image_validator import (
    ImageLimits,
    ImageValidationError,
    validate_image_bytes,
    validate_image_path,
)


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (20, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (20, 40, 60, 128)).save(buffer, image_format)
    return buffer.getvalue()


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_accepts_supported_formats(image_format: str) -> None:
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    buffer = io.BytesIO()
    Image.new(mode, (20, 30), "red").save(buffer, image_format)
    result = validate_image_bytes(buffer.getvalue())
    assert result.mode == "RGB"
    assert result.size == (20, 30)


def test_rejects_malformed_data() -> None:
    with pytest.raises(ImageValidationError):
        validate_image_bytes(b"not an image")


def test_rejects_file_size() -> None:
    limits = ImageLimits(max_file_bytes=8)
    with pytest.raises(ImageValidationError, match="size limit"):
        validate_image_bytes(image_bytes(), limits)


def test_rejects_dimension_limit() -> None:
    limits = ImageLimits(max_width=10, max_height=100, max_pixels=1000)
    with pytest.raises(ImageValidationError, match="dimensions"):
        validate_image_bytes(image_bytes(size=(20, 20)), limits)


def test_rejects_pixel_limit() -> None:
    limits = ImageLimits(max_width=100, max_height=100, max_pixels=30)
    with pytest.raises(ImageValidationError, match="too many pixels"):
        validate_image_bytes(image_bytes(size=(6, 6)), limits)


def test_does_not_trust_extension(tmp_path) -> None:
    disguised = tmp_path / "garment.exe"
    disguised.write_bytes(image_bytes())
    assert validate_image_path(disguised).size == (20, 30)
