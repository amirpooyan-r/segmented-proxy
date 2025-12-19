from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Dict, Tuple
from urllib.parse import urlsplit


@dataclass(frozen=True)
class HttpRequest:
    method: str
    target: str
    version: str
    headers: Dict[str, str]


def parse_http_request(raw: bytes) -> HttpRequest:
    """
    Parse HTTP request line and headers.
    Returns HttpRequest with lowercase header keys.
    """
    header_part, _, _ = raw.partition(b"\r\n\r\n")
    lines = header_part.split(b"\r\n")
    if not lines:
        raise ValueError("Empty request")

    request_line = lines[0].decode("iso-8859-1")
    parts = request_line.split(" ", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid request line: {request_line}")

    method, target, version = parts

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line or b":" not in line:
            continue
        k, v = line.split(b":", 1)
        headers[k.decode("iso-8859-1").strip().lower()] = v.decode("iso-8859-1").strip()

    return HttpRequest(method=method, target=target, version=version, headers=headers)


def send_http_error(client_sock: socket.socket, status: int, message: str) -> None:
    body = (message + "\n").encode("utf-8")
    response = (
        f"HTTP/1.1 {status} {message}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8") + body
    client_sock.sendall(response)


def split_absolute_http_url(target: str) -> Tuple[str, int, str]:
    """
    Convert absolute-form URL into (host, port, path_with_query)
    Supports http:// only.
    """
    if not target.startswith("http://"):
        raise ValueError("Only http:// absolute-form supported")

    u = urlsplit(target)
    host = u.hostname
    if not host:
        raise ValueError("Invalid URL")

    port = u.port or 80

    path = u.path or "/"
    if u.query:
        path += "?" + u.query

    return host, port, path

def split_headers_and_body(raw: bytes) -> tuple[bytes, bytes]:
    """
    Split raw request into (header_bytes_including_crlfcrlf, initial_body_bytes).
    """
    head, sep, tail = raw.partition(b"\r\n\r\n")
    if not sep:
        return raw, b""
    return head + sep, tail
