import pytest

from segmentedproxy.http import (
    parse_http_request,
    split_absolute_http_url,
)


def test_parse_http_request_basic():
    raw = (
        b"GET http://example.com/path HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"User-Agent: curl/8.0\r\n"
        b"\r\n"
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
