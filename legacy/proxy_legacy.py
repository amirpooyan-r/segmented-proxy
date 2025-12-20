"""
LEGACY / ARCHIVE

This file is kept for historical reference only.
It is not used by the SegmentedProxy package.

See src/segmentedproxy/ for the maintained implementation.
"""

from __future__ import annotations

import logging
import select
import socket
import threading
import time
from contextlib import closing
from urllib.parse import urlsplit

# =========================
# Helpers (module-level)
# =========================


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


def parse_http_request(raw: bytes) -> tuple[str, str, str, dict[str, str]]:
    """
    Parse HTTP request line and headers.
    Returns (method, target, version, headers)
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

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line or b":" not in line:
            continue
        k, v = line.split(b":", 1)
        headers[k.decode("iso-8859-1").strip().lower()] = v.decode("iso-8859-1").strip()

    return method, target, version, headers


def send_http_error(client_sock: socket.socket, status: int, message: str) -> None:
    body = (message + "\n").encode("utf-8")
    response = (
        f"HTTP/1.1 {status} {message}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode() + body
    client_sock.sendall(response)


# =========================
# Proxy Server
# =========================


class ProxyServer:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        connect_timeout: float = 10.0,
        idle_timeout: float = 60.0,
        max_connections: int = 200,
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.connect_timeout = connect_timeout
        self.idle_timeout = idle_timeout
        self.max_connections = max_connections
        self._sem = threading.BoundedSemaphore(max_connections)

    # -------------------------
    # Main accept loop
    # -------------------------

    def serve_forever(self) -> None:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.listen_host, self.listen_port))
            s.listen(128)

            logging.info("Listening on %s:%d", self.listen_host, self.listen_port)

            while True:
                client_sock, client_addr = s.accept()

                if not self._sem.acquire(blocking=False):
                    logging.warning("Too many connections; rejecting %s", client_addr)
                    client_sock.close()
                    continue

                t = threading.Thread(
                    target=self._handle_client_wrapper,
                    args=(client_sock, client_addr),
                    daemon=True,
                )
                t.start()

    def _handle_client_wrapper(self, client_sock: socket.socket, client_addr) -> None:
        try:
            self.handle_client(client_sock, client_addr)
        except Exception:
            logging.exception("Unhandled error for client %s", client_addr)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            self._sem.release()

    # -------------------------
    # Client handling
    # -------------------------

    def handle_client(self, client_sock: socket.socket, client_addr) -> None:
        client_sock.settimeout(self.idle_timeout)

        raw = recv_until(client_sock, b"\r\n\r\n")
        if not raw:
            return

        method, target, version, headers = parse_http_request(raw)
        logging.info("Request %s %s from %s", method, target, client_addr)

        if method.upper() == "CONNECT":
            self._handle_connect(client_sock, target)
            return

        self._handle_http(client_sock, method, target, version, headers)

    # -------------------------
    # HTTP proxying
    # -------------------------

    def _handle_http(
        self,
        client_sock: socket.socket,
        method: str,
        target: str,
        version: str,
        headers: dict[str, str],
    ) -> None:
        if not target.startswith("http://"):
            send_http_error(client_sock, 400, "Only http:// absolute-form supported")
            return

        u = urlsplit(target)
        host = u.hostname
        port = u.port or 80
        path = u.path or "/"
        if u.query:
            path += "?" + u.query

        if not host:
            send_http_error(client_sock, 400, "Invalid URL")
            return

        logging.debug("HTTP forward %s:%d %s", host, port, path)

        headers.pop("proxy-connection", None)
        headers["host"] = host if port == 80 else f"{host}:{port}"
        headers["connection"] = "close"

        request_line = f"{method} {path} {version}\r\n"
        header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        forward = (request_line + header_blob + "\r\n").encode("iso-8859-1")

        try:
            with socket.create_connection((host, port), timeout=self.connect_timeout) as upstream:
                upstream.settimeout(self.idle_timeout)
                upstream.sendall(forward)

                while True:
                    data = upstream.recv(4096)
                    if not data:
                        break
                    client_sock.sendall(data)

        except socket.gaierror:
            send_http_error(client_sock, 502, "DNS resolution failed")
        except TimeoutError:
            send_http_error(client_sock, 504, "Upstream timeout")
        except OSError:
            send_http_error(client_sock, 502, "Upstream connection failed")

    # -------------------------
    # HTTPS CONNECT tunneling
    # -------------------------

    def _handle_connect(self, client_sock: socket.socket, target: str) -> None:
        if ":" not in target:
            send_http_error(client_sock, 400, "CONNECT target must be host:port")
            return

        host, port_s = target.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            send_http_error(client_sock, 400, "Invalid CONNECT port")
            return

        logging.debug("CONNECT tunnel %s:%d", host, port)

        try:
            upstream = socket.create_connection((host, port), timeout=self.connect_timeout)
            upstream.settimeout(self.idle_timeout)
        except socket.gaierror:
            send_http_error(client_sock, 502, "DNS resolution failed")
            return
        except TimeoutError:
            send_http_error(client_sock, 504, "Upstream timeout")
            return
        except OSError:
            send_http_error(client_sock, 502, "Upstream connection failed")
            return

        client_sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")

        try:
            self._relay_bidirectional(client_sock, upstream)
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    # -------------------------
    # Tunnel relay
    # -------------------------

    def _relay_bidirectional(
        self,
        a: socket.socket,
        b: socket.socket,
    ) -> None:
        a.setblocking(False)
        b.setblocking(False)

        last_activity = time.monotonic()
        sockets = [a, b]

        while True:
            if time.monotonic() - last_activity > self.idle_timeout:
                logging.debug("Tunnel idle timeout")
                return

            readable, _, exceptional = select.select(sockets, [], sockets, 1.0)

            if exceptional:
                return

            for src in readable:
                dst = b if src is a else a
                try:
                    data = src.recv(4096)
                except BlockingIOError:
                    continue
                except OSError:
                    return

                if not data:
                    return

                last_activity = time.monotonic()
                try:
                    dst.sendall(data)
                except OSError:
                    return
