from __future__ import annotations

import argparse
import itertools
import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import (
    parse_http_request,
    send_http_error,
    split_headers_and_body,
)
from segmentedproxy.net import recv_until
from segmentedproxy.server import ThreadedTCPServer


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="segproxy",
        description="SegmentedProxy - educational HTTP/HTTPS proxy with safe defaults.",
    )
    p.add_argument("--listen-host", default="127.0.0.1")
    p.add_argument("--listen-port", type=int, default=8080)
    p.add_argument("--connect-timeout", type=float, default=10.0)
    p.add_argument("--idle-timeout", type=float, default=60.0)
    p.add_argument("--max-connections", type=int, default=200)
    p.add_argument("--log-level", default="INFO")
    p.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Allow domain or suffix (e.g. example.com or .example.com)",
    )
    p.add_argument(
        "--deny-domain",
        action="append",
        default=[],
        help="Deny domain or suffix (e.g. ads.com or .ads.com)",
    )
    p.add_argument(
        "--deny-private",
        action="store_true",
        default=True,
        help="Block private/loopback/reserved IPs (default: on)",
    )
    p.add_argument(
        "--allow-private",
        action="store_true",
        default=False,
        help="Allow private/loopback/reserved IPs (disables deny-private)",
    )

    return p


def make_settings(args: argparse.Namespace) -> Settings:
    return Settings(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        connect_timeout=args.connect_timeout,
        idle_timeout=args.idle_timeout,
        max_connections=args.max_connections,
        allow_domains=tuple(args.allow_domain),
        deny_domains=tuple(args.deny_domain),
        deny_private=(not args.allow_private),
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = make_settings(args)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("Starting SegmentedProxy on %s:%s", settings.listen_host, settings.listen_port)

    conn_ids = itertools.count(1)

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

        cid = next(conn_ids)
        logging.info("[C%05d] %s %s from %s", cid, req.method, req.target, client_addr)

        # Read request body if present (Content-Length)
        body = body_initial
        cl = req.headers.get("content-length")
        te = req.headers.get("transfer-encoding")

        if te and te.lower() != "identity":
            # We'll add chunked support later; for now be correct and explicit.
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

    server = ThreadedTCPServer(
        listen_host=settings.listen_host,
        listen_port=settings.listen_port,
        handler=handle_client,
        max_connections=settings.max_connections,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received, shutting down...")
    finally:
        server.shutdown()
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()
