from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QUrl
from PySide6.QtGui import QImage, QPixmap

LOGGER = logging.getLogger(__name__)


class DropKind(str, Enum):
    BYTES = "bytes"
    LOCAL_FILE = "local_file"
    REMOTE_URL = "remote_url"


@dataclass(frozen=True, slots=True)
class DropCandidate:
    kind: DropKind
    value: bytes | str


def _qimage_to_png(image_data: object) -> bytes | None:
    if isinstance(image_data, QPixmap):
        image = image_data.toImage()
    else:
        image = QImage(image_data) if not isinstance(image_data, QImage) else image_data
    if image.isNull():
        return None
    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    try:
        if not image.save(buffer, "PNG"):
            return None
        return bytes(payload)
    finally:
        buffer.close()


def parse_mime_data(mime: QMimeData) -> list[DropCandidate]:
    """Return candidates in safest/preferred order without dereferencing URLs."""
    LOGGER.debug("drop_mime formats=%s", sorted(str(item) for item in mime.formats()))
    candidates: list[DropCandidate] = []

    if mime.hasImage():
        png = _qimage_to_png(mime.imageData())
        if png:
            candidates.append(DropCandidate(DropKind.BYTES, png))

    if mime.hasUrls():
        for url in mime.urls():
            if not isinstance(url, QUrl):
                continue
            if url.isLocalFile():
                candidates.append(DropCandidate(DropKind.LOCAL_FILE, url.toLocalFile()))
            elif url.scheme().lower() == "https":
                candidates.append(DropCandidate(DropKind.REMOTE_URL, url.toString()))

    if mime.hasText():
        text = mime.text().strip()
        if text.lower().startswith("https://") and not any(
            item.kind is DropKind.REMOTE_URL and item.value == text for item in candidates
        ):
            candidates.append(DropCandidate(DropKind.REMOTE_URL, text))

    return candidates
