import logging

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import HttpRequest


class FakeSocket:
    def __init__(self, recv_chunks: list[bytes] | None = None) -> None:
        self.sent: list[bytes] = []
        self._recv_chunks = list(recv_chunks or [])

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, _size: int) -> bytes:
        if self._recv_chunks:
            return self._recv_chunks.pop(0)
        return b""

    def settimeout(self, _timeout: float) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None


def _access_lines(caplog) -> list[str]:
    return [
        rec.message
        for rec in caplog.records
        if rec.levelno == logging.INFO and "ACCESS" in rec.message
    ]


def test_access_log_http_forward_enabled(caplog, monkeypatch) -> None:
    upstream = FakeSocket(recv_chunks=[b"HTTP/1.1 200 OK\r\n\r\nhi", b""])
    monkeypatch.setattr("segmentedproxy.handlers.open_upstream", lambda *a, **k: upstream)
    settings = Settings(deny_private=False, access_log=True)
    req = HttpRequest(
        method="GET",
        target="http://example.com/",
        version="HTTP/1.1",
        headers={"host": "example.com"},
    )

    with caplog.at_level(logging.INFO):
        handle_http_forward(FakeSocket(), req, b"", settings, request_id="deadbeef")

    lines = _access_lines(caplog)
    assert len(lines) == 1
    assert "ACCESS" in lines[0]
    assert "rid=deadbeef" in lines[0]
    assert "method=GET" in lines[0]


def test_access_log_http_forward_disabled(caplog, monkeypatch) -> None:
    upstream = FakeSocket(recv_chunks=[b"HTTP/1.1 200 OK\r\n\r\nhi", b""])
    monkeypatch.setattr("segmentedproxy.handlers.open_upstream", lambda *a, **k: upstream)
    settings = Settings(deny_private=False, access_log=False)
    req = HttpRequest(
        method="GET",
        target="http://example.com/",
        version="HTTP/1.1",
        headers={"host": "example.com"},
    )

    with caplog.at_level(logging.INFO):
        handle_http_forward(FakeSocket(), req, b"", settings, request_id="deadbeef")

    assert not _access_lines(caplog)


def test_access_log_connect_enabled(caplog, monkeypatch) -> None:
    monkeypatch.setattr("segmentedproxy.handlers.open_upstream", lambda *a, **k: FakeSocket())
    monkeypatch.setattr("segmentedproxy.handlers.perform_upstream_connect", lambda *a, **k: True)
    monkeypatch.setattr("segmentedproxy.handlers.relay_tunnel", lambda *a, **k: None)
    settings = Settings(deny_private=False, access_log=True)

    with caplog.at_level(logging.INFO):
        handle_connect_tunnel(FakeSocket(), "example.com:443", settings, request_id="deadbeef")

    lines = _access_lines(caplog)
    assert len(lines) == 1
    assert "ACCESS" in lines[0]
    assert "rid=deadbeef" in lines[0]
    assert "method=CONNECT" in lines[0]
