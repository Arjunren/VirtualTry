from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from virtual_tryon.imaging.drop_parser import DropCandidate, DropKind
from virtual_tryon.imaging.image_validator import ImageLimits, validate_image_bytes, validate_image_path
from virtual_tryon.imaging.secure_fetch import fetch_remote_image


class ImageTaskSignals(QObject):
    loaded = Signal(str, object)
    failed = Signal(str, str)


class ImageLoadTask(QRunnable):
    def __init__(
        self,
        target: str,
        candidates: list[DropCandidate],
        limits: ImageLimits,
        allow_remote: bool,
    ) -> None:
        super().__init__()
        self.target = target
        self.candidates = candidates
        self.limits = limits
        self.allow_remote = allow_remote
        self.signals = ImageTaskSignals()

    @Slot()
    def run(self) -> None:
        last_error = "No supported image data was found."
        for candidate in self.candidates:
            try:
                image: Image.Image
                if candidate.kind is DropKind.BYTES:
                    image = validate_image_bytes(bytes(candidate.value), self.limits)
                elif candidate.kind is DropKind.LOCAL_FILE:
                    image = validate_image_path(str(candidate.value), self.limits)
                else:
                    if not self.allow_remote:
                        raise ValueError("Remote image loading is disabled in Settings.")
                    payload = fetch_remote_image(str(candidate.value), self.limits)
                    image = validate_image_bytes(payload, self.limits)
                self.signals.loaded.emit(self.target, image)
                return
            except Exception as error:
                last_error = str(error)
        self.signals.failed.emit(self.target, last_error)
