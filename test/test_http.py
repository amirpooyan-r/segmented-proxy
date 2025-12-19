import pytest

from segmentedproxy.http import parse_http_request, split_absolute_http_url, split_headers_and_body


def test_parse_http_request_basic():
    raw = (
        b"GET http://example.com/path HTTP/1.1\r\nHost: example.com\r\nUser-Agent: curl/8.0\r\n\r\n"
    )

    req = parse_http_request(raw)

    assert req.method == "GET"
    assert req.target == "http://example.com/path"
    assert req.version == "HTTP/1.1"
    assert req.headers["host"] == "example.com"
    assert req.headers["user-agent"] == "curl/8.0"


def test_parse_http_request_invalid():
    with pytest.raises(ValueError):
        parse_http_request(b"\r\n")


def test_split_absolute_http_url():
    host, port, path = split_absolute_http_url("http://example.com/test?q=1")

    assert host == "example.com"
    assert port == 80
    assert path == "/test?q=1"


def test_split_absolute_http_url_invalid():
    with pytest.raises(ValueError):
        split_absolute_http_url("/relative/path")


def test_split_headers_and_body_no_body():
    raw = b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n"
    header, body = split_headers_and_body(raw)
    assert header.endswith(b"\r\n\r\n")
    assert body == b""


def test_split_headers_and_body_with_body():
    raw = (
        b"POST http://example.com/post HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Content-Length: 11\r\n"
        b"\r\n"
        b"hello=world"
    )
    header, body = split_headers_and_body(raw)
    assert header.endswith(b"\r\n\r\n")
    assert body == b"hello=world"
