from __future__ import annotations

import argparse
import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.http import parse_http_request, send_http_error
from segmentedproxy.net import recv_until
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
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
    return p


def make_settings(args: argparse.Namespace) -> Settings:
    return Settings(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        connect_timeout=args.connect_timeout,
        idle_timeout=args.idle_timeout,
        max_connections=args.max_connections,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = make_settings(args)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("Starting SegmentedProxy on %s:%s", settings.listen_host, settings.listen_port)

    def handle_client(client_sock: socket.socket, client_addr) -> None:
        client_sock.settimeout(settings.idle_timeout)

        raw = recv_until(client_sock, b"\r\n\r\n")
        if not raw:
            return

        try:
            req = parse_http_request(raw)
        except ValueError as e:
            send_http_error(client_sock, 400, str(e))
            return

        logging.info("Request %s %s from %s", req.method, req.target, client_addr)

        if req.method.upper() == "CONNECT":
            handle_connect_tunnel(client_sock, req.target, settings)
        else:
            handle_http_forward(client_sock, req, settings)

    server = ThreadedTCPServer(
        listen_host=settings.listen_host,
        listen_port=settings.listen_port,
        handler=handle_client,
        max_connections=settings.max_connections,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
