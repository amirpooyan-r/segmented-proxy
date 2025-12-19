from __future__ import annotations

import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.http import HttpRequest, send_http_error, split_absolute_http_url
from segmentedproxy.tunnel import open_upstream, parse_connect_target, relay_bidirectional


def handle_http_forward(
    client_sock: socket.socket,
    req: HttpRequest,
    body: bytes,
    settings: Settings,
) -> None:
    try:
        host, port, path = split_absolute_http_url(req.target)
    except ValueError as e:
        send_http_error(client_sock, 400, str(e))
        return

    headers: dict[str, str] = dict(req.headers)
    headers.pop("proxy-connection", None)

    # Remove hop-by-hop headers (RFC 7230)
    hop_by_hop = {
        "connection",
        "proxy-connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
    }
    for h in hop_by_hop:
        headers.pop(h, None)

    # If client sent "Connection: x,y", those named headers are hop-by-hop too
    conn_hdr = req.headers.get("connection")
    if conn_hdr:
        for token in conn_hdr.split(","):
            headers.pop(token.strip().lower(), None)

    headers["host"] = host if port == 80 else f"{host}:{port}"
    headers["connection"] = "close"

    request_line = f"{req.method} {path} {req.version}\r\n"
    header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    forward = (request_line + header_blob + "\r\n").encode("iso-8859-1")

    logging.debug("HTTP forward %s:%d %s", host, port, path)

    try:
        with socket.create_connection((host, port), timeout=settings.connect_timeout) as upstream:
            upstream.settimeout(settings.idle_timeout)
            upstream.sendall(forward)
            if body:
                upstream.sendall(body)

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


def handle_connect_tunnel(
    client_sock: socket.socket,
    target: str,
    settings: Settings,
) -> None:
    try:
        host, port = parse_connect_target(target)
    except Exception:
        send_http_error(client_sock, 400, "CONNECT target must be host:port")
        return

    logging.debug("CONNECT tunnel %s:%d", host, port)

    try:
        upstream = open_upstream(host, port, settings.connect_timeout, settings.idle_timeout)
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
        relay_bidirectional(client_sock, upstream, idle_timeout=settings.idle_timeout)
    finally:
        try:
            upstream.close()
        except Exception:
            pass
