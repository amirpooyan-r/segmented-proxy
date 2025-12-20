import os
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import parse_http_request, send_http_error, split_headers_and_body
from segmentedproxy.net import recv_until
from segmentedproxy.server import ThreadedTCPServer


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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _gen_self_signed_cert(tmpdir: str) -> tuple[str, str]:
    cert_path = os.path.join(tmpdir, "cert.pem")
    key_path = os.path.join(tmpdir, "key.pem")

    # Generate a self-signed cert valid for localhost (CN=localhost)
    subprocess.check_call(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_path,
            "-out",
            cert_path,
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ]
    )
    return cert_path, key_path


def _start_https_server(port: int, cert_path: str, key_path: str) -> HTTPServer:
    httpd = HTTPServer(("127.0.0.1", port), HelloTLSHandler)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _start_proxy(port: int) -> ThreadedTCPServer:
    settings = Settings(
        listen_host="127.0.0.1",
        listen_port=port,
        connect_timeout=5.0,
        idle_timeout=5.0,
        max_connections=50,
        allow_domains=tuple(),
        deny_domains=tuple(),
        deny_private=False,  # allow localhost for test
    )

    def handle_client(client_sock: socket.socket, client_addr) -> None:
        client_sock.settimeout(settings.idle_timeout)

        raw = recv_until(client_sock, b"\r\n\r\n")
        if not raw:
            return

        header_bytes, body_initial = split_headers_and_body(raw)

        try:
            req = parse_http_request(header_bytes)
        except ValueError as e:
            send_http_error(client_sock, 400, str(e))
            return

        # body support (Content-Length only)
        body = body_initial
        cl = req.headers.get("content-length")
        te = req.headers.get("transfer-encoding")
        if te and te.lower() != "identity":
            send_http_error(client_sock, 501, "Transfer-Encoding not supported yet")
            return
        if cl:
            total = int(cl)
            remaining = total - len(body)
            while remaining > 0:
                chunk = client_sock.recv(min(4096, remaining))
                if not chunk:
                    break
                body += chunk
                remaining -= len(chunk)

        if req.method.upper() == "CONNECT":
            handle_connect_tunnel(client_sock, req.target, settings)
        else:
            handle_http_forward(client_sock, req, body, settings)

    server = ThreadedTCPServer("127.0.0.1", port, handler=handle_client, max_connections=50)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _https_get_via_connect(proxy_port: int, host: str, port: int) -> bytes:
    """
    1) Send CONNECT to proxy
    2) Wrap the tunnel with TLS (no verification, self-signed)
    3) Send HTTPS GET and read response
    """
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=5.0) as s:
        connect_req = (
            f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        s.sendall(connect_req)

        # Read CONNECT response headers
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk

        assert b"200" in resp.split(b"\r\n", 1)[0]

        # Now tunnel is established; speak TLS over same socket
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with ctx.wrap_socket(s, server_hostname=host) as tls:
            req = (f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n").encode("ascii")
            tls.sendall(req)

            data = b""
            while True:
                chunk = tls.recv(4096)
                if not chunk:
                    break
                data += chunk
            return data


@pytest.mark.skipif(
    subprocess.call(["which", "openssl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    != 0,
    reason="openssl not available",
)
def test_https_connect_tunnel():
    origin_port = _free_port()
    proxy_port = _free_port()

    with tempfile.TemporaryDirectory() as tmp:
        cert_path, key_path = _gen_self_signed_cert(tmp)

        httpsd = _start_https_server(origin_port, cert_path, key_path)
        proxy = _start_proxy(proxy_port)

        try:
            time.sleep(0.2)

            resp = _https_get_via_connect(proxy_port, "127.0.0.1", origin_port)
            assert b"200" in resp.split(b"\r\n", 1)[0]
            assert b"hello-from-tls-origin" in resp
        finally:
            proxy.shutdown()
            httpsd.shutdown()
