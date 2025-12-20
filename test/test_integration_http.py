import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import parse_http_request, send_http_error, split_headers_and_body
from segmentedproxy.main import make_settings  # noqa: F401  (import check)
from segmentedproxy.net import recv_until
from segmentedproxy.server import ThreadedTCPServer


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b"hello-from-origin"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        # silence test output
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_http_server(port: int) -> HTTPServer:
    httpd = HTTPServer(("127.0.0.1", port), HelloHandler)
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
        deny_private=False,  # IMPORTANT: allow localhost for integration test
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


def _http_via_proxy(proxy_port: int, url: str) -> bytes:
    """
    Minimal HTTP client that speaks to an HTTP proxy in absolute-form.
    """
    host = "127.0.0.1"
    with socket.create_connection((host, proxy_port), timeout=5.0) as s:
        req = (f"GET {url} HTTP/1.1\r\nHost: dummy\r\nConnection: close\r\n\r\n").encode("ascii")
        s.sendall(req)
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
    return resp


def test_http_get_through_proxy():
    origin_port = _free_port()
    proxy_port = _free_port()

    httpd = _start_http_server(origin_port)
    proxy = _start_proxy(proxy_port)

    try:
        # give threads a moment
        time.sleep(0.2)

        url = f"http://127.0.0.1:{origin_port}/"
        resp = _http_via_proxy(proxy_port, url)

        assert b"200" in resp.split(b"\r\n", 1)[0]
        assert b"hello-from-origin" in resp
    finally:
        proxy.shutdown()
        httpd.shutdown()
