from __future__ import annotations

import os
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import parse_http_request, send_http_error, split_headers_and_body
from segmentedproxy.net import recv_until
from segmentedproxy.server import ThreadedTCPServer


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_http_server(port: int, handler_cls: type[BaseHTTPRequestHandler]) -> HTTPServer:
    httpd = HTTPServer(("127.0.0.1", port), handler_cls)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def gen_self_signed_cert(tmpdir: str) -> tuple[str, str]:
    cert_path = os.path.join(tmpdir, "cert.pem")
    key_path = os.path.join(tmpdir, "key.pem")
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


def start_https_server(
    port: int, handler_cls: type[BaseHTTPRequestHandler], cert_path: str, key_path: str
) -> HTTPServer:
    httpd = HTTPServer(("127.0.0.1", port), handler_cls)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def start_proxy(
    port: int,
    *,
    deny_private: bool = False,
    allow_domains: tuple[str, ...] = tuple(),
    deny_domains: tuple[str, ...] = tuple(),
) -> ThreadedTCPServer:
    settings = Settings(
        listen_host="127.0.0.1",
        listen_port=port,
        connect_timeout=5.0,
        idle_timeout=5.0,
        max_connections=50,
        allow_domains=allow_domains,
        deny_domains=deny_domains,
        deny_private=deny_private,
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

        # Content-Length only (integration tests keep it simple)
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


def http_via_proxy(proxy_port: int, url: str) -> bytes:
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=5.0) as s:
        req = (f"GET {url} HTTP/1.1\r\nHost: dummy\r\nConnection: close\r\n\r\n").encode("ascii")
        s.sendall(req)
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        return resp


def https_get_via_connect(proxy_port: int, host: str, port: int) -> bytes:
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=5.0) as s:
        connect_req = (
            f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        s.sendall(connect_req)

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk

        if b"200" not in resp.split(b"\r\n", 1)[0]:
            return resp

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


def openssl_available() -> bool:
    return (
        subprocess.call(["which", "openssl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        == 0
    )


def temp_certpair() -> tuple[tempfile.TemporaryDirectory, str, str]:
    tmp = tempfile.TemporaryDirectory()
    cert_path, key_path = gen_self_signed_cert(tmp.name)
    return tmp, cert_path, key_path


def sleep_brief() -> None:
    time.sleep(0.2)
