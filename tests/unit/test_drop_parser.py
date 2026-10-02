from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QImage

from virtual_tryon.imaging.drop_parser import DropKind, parse_mime_data


def test_parses_local_file_url(tmp_path) -> None:
    mime = QMimeData()
    path = tmp_path / "person.png"
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    result = parse_mime_data(mime)
    assert result[0].kind is DropKind.LOCAL_FILE
    assert Path(str(result[0].value)) == path


def test_prefers_direct_image_bytes() -> None:
    mime = QMimeData()
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0xFF00FF)
    mime.setImageData(image)
    mime.setUrls([QUrl("https://example.com/image.png")])
    result = parse_mime_data(mime)
    assert result[0].kind is DropKind.BYTES
    assert bytes(result[0].value).startswith(b"\x89PNG")


def test_parses_https_text_only() -> None:
    mime = QMimeData()
    mime.setText("https://example.com/garment.webp")
    result = parse_mime_data(mime)
    assert result == [result[0]]
    assert result[0].kind is DropKind.REMOTE_URL


def test_rejects_http_text() -> None:
    mime = QMimeData()
    mime.setText("http://example.com/image.png")
    assert parse_mime_data(mime) == []
