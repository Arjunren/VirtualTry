from __future__ import annotations

import socket

import pytest

from virtual_tryon.imaging.secure_fetch import RemoteImageError, validate_remote_url


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/image.png",
        "https://localhost/image.png",
        "https://127.0.0.1/image.png",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.1/image.png",
        "https://192.168.1.1/image.png",
        "file:///C:/image.png",
        "https://user:secret@example.com/image.png",
        "https://example.com:8443/image.png",
    ],
)
def test_blocks_unsafe_destinations(url: str) -> None:
    with pytest.raises(RemoteImageError):
        validate_remote_url(url)


def test_accepts_public_https_with_controlled_dns() -> None:
    def resolver(host: str, port: int, type: int) -> list[tuple]:
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

    host, port, path, addresses = validate_remote_url("https://images.example.com/a.png?q=1", resolver)
    assert (host, port, path) == ("images.example.com", 443, "/a.png?q=1")
    assert addresses == ("8.8.8.8",)


def test_blocks_mixed_public_private_dns() -> None:
    def resolver(host: str, port: int, type: int) -> list[tuple]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", port)),
        ]

    with pytest.raises(RemoteImageError):
        validate_remote_url("https://example.com/a.png", resolver)
