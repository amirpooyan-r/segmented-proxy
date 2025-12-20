from __future__ import annotations

import logging
import socket
from collections.abc import Callable

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import (
    parse_http_request,
    send_http_error,
    split_headers_and_body,
)
from segmentedproxy.net import recv_until


def make_client_handler(settings: Settings) -> Callable[[socket.socket, tuple], None]:
    """
    Factory that returns a connection handler function bound to given settings.

    This is the single source of truth for:
    - parsing incoming proxy requests
    - reading request bodies
    - routing CONNECT vs HTTP
    """

    def handle_client(client_sock: socket.socket, client_addr) -> None:
        client_sock.settimeout(settings.idle_timeout)

        try:
            raw = recv_until(client_sock, b"\r\n\r\n")
            if not raw:
                return

            header_bytes, body_initial = split_headers_and_body(raw)

            try:
                req = parse_http_request(header_bytes)
            except ValueError as e:
                send_http_error(client_sock, 400, str(e))
                return

            logging.info(
                "%s %s from %s",
                req.method,
                req.target,
                client_addr,
            )

            # Read request body (Content-Length only)
            body = body_initial
            cl = req.headers.get("content-length")
            te = req.headers.get("transfer-encoding")

            if te and te.lower() != "identity":
                send_http_error(client_sock, 501, "Transfer-Encoding not supported yet")
                return

            if cl:
                try:
                    total = int(cl)
                except ValueError:
                    send_http_error(client_sock, 400, "Invalid Content-Length")
                    return

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

        except TimeoutError:
            logging.debug("Client timeout: %s", client_addr)
        except OSError as e:
            logging.debug("Client socket error %s: %s", client_addr, e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    return handle_client
