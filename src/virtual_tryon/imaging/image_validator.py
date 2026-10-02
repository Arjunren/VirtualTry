from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageValidationError(ValueError):
    """Raised when untrusted input is not an acceptable image."""


@dataclass(frozen=True, slots=True)
class ImageLimits:
    max_file_bytes: int = 20 * 1024 * 1024
    max_width: int = 8192
    max_height: int = 8192
    max_pixels: int = 40_000_000


def _decode(data: bytes, limits: ImageLimits) -> Image.Image:
    if not data:
        raise ImageValidationError("The image is empty.")
    if len(data) > limits.max_file_bytes:
        raise ImageValidationError("The image exceeds the configured 20 MB size limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            image_format = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ImageValidationError("The file is not a valid supported image.") from error

    if image_format not in ALLOWED_FORMATS:
        raise ImageValidationError("Only JPEG, PNG, and WebP images are supported.")
    if width <= 0 or height <= 0 or width > limits.max_width or height > limits.max_height:
        raise ImageValidationError("The image dimensions exceed the configured safety limit.")
    if width * height > limits.max_pixels:
        raise ImageValidationError("The decoded image contains too many pixels.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            decoded = Image.open(io.BytesIO(data))
            decoded.load()
            return decoded.convert("RGB")
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ImageValidationError("The image could not be decoded safely.") from error


def validate_image_bytes(data: bytes, limits: ImageLimits | None = None) -> Image.Image:
    return _decode(data, limits or ImageLimits())


def validate_image_path(path: str | Path, limits: ImageLimits | None = None) -> Image.Image:
    image_limits = limits or ImageLimits()
    candidate = Path(path)
    try:
        if not candidate.is_file():
            raise ImageValidationError("The dropped item is not a file.")
        if candidate.stat().st_size > image_limits.max_file_bytes:
            raise ImageValidationError("The image exceeds the configured 20 MB size limit.")
        return _decode(candidate.read_bytes(), image_limits)
    except ImageValidationError:
        raise
    except OSError as error:
        raise ImageValidationError("The image file could not be read.") from error
