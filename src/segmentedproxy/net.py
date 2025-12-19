from __future__ import annotations

import socket


def recv_until(sock: socket.socket, marker: bytes, max_size: int = 65536) -> bytes:
    """
    Receive data until marker is found or connection closes.
    Used to read HTTP headers (CRLFCRLF).
    """
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > max_size:
            raise ValueError("Request headers too large")
    return data
