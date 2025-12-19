from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from segmentedproxy.proxy import ProxyServer


@dataclass(frozen=True)
class Settings:
    listen_host: str
    listen_port: int
    connect_timeout: float
    idle_timeout: float
    max_connections: int
    log_level: str


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="segproxy",
        description="SegmentedProxy - educational HTTP/HTTPS proxy with safe defaults.",
    )
    p.add_argument("--listen-host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p.add_argument("--listen-port", type=int, default=8080, help="Bind port (default: 8080)")
    p.add_argument("--connect-timeout", type=float, default=10.0, help="Upstream connect timeout seconds")
    p.add_argument("--idle-timeout", type=float, default=60.0, help="Idle tunnel timeout seconds")
    p.add_argument("--max-connections", type=int, default=200, help="Max concurrent client connections")
    p.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR")
    return p


def main() -> None:
    args = build_parser().parse_args()

    settings = Settings(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        connect_timeout=args.connect_timeout,
        idle_timeout=args.idle_timeout,
        max_connections=args.max_connections,
        log_level=args.log_level.upper(),
    )

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("Starting SegmentedProxy on %s:%s", settings.listen_host, settings.listen_port)

    server = ProxyServer(
        listen_host=settings.listen_host,
        listen_port=settings.listen_port,
        connect_timeout=settings.connect_timeout,
        idle_timeout=settings.idle_timeout,
        max_connections=settings.max_connections,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
