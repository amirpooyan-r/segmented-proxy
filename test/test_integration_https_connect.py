from http.server import BaseHTTPRequestHandler

import pytest

from test.helpers import (
    free_port,
    https_get_via_connect,
    openssl_available,
    sleep_brief,
    start_https_server,
    start_proxy,
    temp_certpair,
)


class HelloTLSHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b"hello-from-tls-origin"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


@pytest.mark.skipif(not openssl_available(), reason="openssl not available")
def test_https_connect_tunnel():
    origin_port = free_port()
    proxy_port = free_port()

    tmp, cert_path, key_path = temp_certpair()
    httpsd = start_https_server(origin_port, HelloTLSHandler, cert_path, key_path)
    proxy = start_proxy(proxy_port, deny_private=False)

    try:
        sleep_brief()
        resp = https_get_via_connect(proxy_port, "127.0.0.1", origin_port)
        assert b"200" in resp.split(b"\r\n", 1)[0]
        assert b"hello-from-tls-origin" in resp
    finally:
        proxy.shutdown()
        httpsd.shutdown()
        tmp.cleanup()
