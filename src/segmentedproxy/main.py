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
    parser = argparse.ArgumentParser(
        prog="segproxy",
        description="SegmentedProxy - educational HTTP/HTTPS proxy with safe defaults.",
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8080)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--idle-timeout", type=float, default=60.0)
    parser.add_argument("--max-connections", type=int, default=200)
    parser.add_argument("--log-level", default="INFO")
    return parser


def make_settings(args: argparse.Namespace) -> Settings:
    return Settings(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        connect_timeout=args.connect_timeout,
        idle_timeout=args.idle_timeout,
        max_connections=args.max_connections,
    )


def read_request_body(
    client_sock: socket.socket,
    initial_body: bytes,
    headers: dict[str, str],
) -> bytes:
    """
    Read remaining request body based on Content-Length.
    Reject unsupported Transfer-Encoding.
    """
    body = initial_body

    transfer_encoding = headers.get("transfer-encoding")
    if transfer_encoding and transfer_encoding.lower() != "identity":
        raise ValueError("Transfer-Encoding not supported")

    content_length = headers.get("content-length")
    if not content_length:
        return body

    try:
        total_length = int(content_length)
    except ValueError as exc:
        raise ValueError("Invalid Content-Length") from exc

    remaining = total_length - len(body)
    while remaining > 0:
        chunk = client_sock.recv(min(4096, remaining))
        if not chunk:
            break
        body += chunk
        remaining -= len(chunk)

    return body


def handle_client_factory(settings: Settings):
    """
    Factory returning a connection handler bound to Settings.
    """

    conn_ids = itertools.count(1)

    def handle_client(client_sock: socket.socket, client_addr) -> None:
        client_sock.settimeout(settings.idle_timeout)

        raw = recv_until(client_sock, b"\r\n\r\n")
        if not raw:
            return

        header_bytes, body_initial = split_headers_and_body(raw)

        try:
            request = parse_http_request(header_bytes)
        except ValueError as exc:
            send_http_error(client_sock, 400, str(exc))
            return

        cid = next(conn_ids)
        logging.info(
            "[C%05d] %s %s from %s",
            cid,
            request.method,
            request.target,
            client_addr,
        )

        try:
            body = read_request_body(
                client_sock,
                body_initial,
                request.headers,
            )
        except ValueError as exc:
            send_http_error(client_sock, 400, str(exc))
            return

        if request.method.upper() == "CONNECT":
            handle_connect_tunnel(client_sock, request.target, settings)
        else:
            handle_http_forward(client_sock, request, body, settings)

    return handle_client


def main() -> None:
    args = build_parser().parse_args()
    settings = make_settings(args)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info(
        "Starting SegmentedProxy on %s:%d",
        settings.listen_host,
        settings.listen_port,
    )

    server = ThreadedTCPServer(
        listen_host=settings.listen_host,
        listen_port=settings.listen_port,
        handler=handle_client_factory(settings),
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
