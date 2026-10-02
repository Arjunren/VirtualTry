from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

from virtual_tryon.imaging.image_validator import ALLOWED_MIME_TYPES, ImageLimits


class RemoteImageError(ValueError):
    pass


Resolver = Callable[..., list[tuple]]


def validate_remote_url(url: str, resolver: Resolver = socket.getaddrinfo) -> tuple[str, int, str, tuple[str, ...]]:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise RemoteImageError("Only HTTPS image URLs are allowed.")
    if parsed.username or parsed.password:
        raise RemoteImageError("URLs containing credentials are not allowed.")
    if not parsed.hostname:
        raise RemoteImageError("The image URL has no valid host.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise RemoteImageError("Local network destinations are blocked.")
    port = parsed.port or 443
    if port != 443:
        raise RemoteImageError("Only the standard HTTPS port is allowed.")

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            records = resolver(hostname, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise RemoteImageError("The image host could not be resolved.") from error
        addresses = []
        for record in records:
            try:
                addresses.append(ipaddress.ip_address(record[4][0]))
            except (ValueError, IndexError) as error:
                raise RemoteImageError("The image host resolved unexpectedly.") from error

    if not addresses or any(not address.is_global for address in addresses):
        raise RemoteImageError("Private, loopback, link-local, and reserved destinations are blocked.")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return hostname, port, path, tuple(str(address) for address in addresses)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a prevalidated IP while retaining hostname TLS verification."""

    def __init__(self, hostname: str, port: int, connect_ip: str, context: ssl.SSLContext, timeout: int) -> None:
        super().__init__(hostname, port, timeout=timeout, context=context)
        self._connect_ip = connect_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def fetch_remote_image(url: str, limits: ImageLimits | None = None, max_redirects: int = 3) -> bytes:
    image_limits = limits or ImageLimits()
    current = url
    context = ssl.create_default_context()

    for redirect_count in range(max_redirects + 1):
        host, port, path, addresses = validate_remote_url(current)
        connection = _PinnedHTTPSConnection(host, port, addresses[0], context=context, timeout=10)
        try:
            connection.request(
                "GET",
                path,
                headers={"Accept": "image/jpeg,image/png,image/webp", "User-Agent": "VirtualTry/0.1"},
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect_count >= max_redirects:
                    raise RemoteImageError("The image URL redirected too many times.")
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise RemoteImageError(f"The image server returned HTTP {response.status}.")

            mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if mime not in ALLOWED_MIME_TYPES:
                raise RemoteImageError("The remote resource is not a supported image type.")
            content_length = response.getheader("Content-Length")
            if content_length and int(content_length) > image_limits.max_file_bytes:
                raise RemoteImageError("The remote image exceeds the configured size limit.")

            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, image_limits.max_file_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > image_limits.max_file_bytes:
                    raise RemoteImageError("The remote image exceeds the configured size limit.")
            return b"".join(chunks)
        except (OSError, http.client.HTTPException, ValueError) as error:
            if isinstance(error, RemoteImageError):
                raise
            raise RemoteImageError("The remote image could not be downloaded securely.") from error
        finally:
            connection.close()

    raise RemoteImageError("The image URL redirected too many times.")
