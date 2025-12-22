from __future__ import annotations

import argparse
import itertools
import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import parse_http_request, send_http_error, split_headers_and_body
from segmentedproxy.net import recv_until
from segmentedproxy.segmentation import SegmentationPolicy, parse_segment_rule
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

    # Segmentation CLI (CONNECT)
    parser.add_argument("--segmentation", default="direct", choices=["direct", "segment_upstream"])
    parser.add_argument("--segment-chunk-size", type=int, default=1024)
    parser.add_argument("--segment-delay-ms", type=int, default=0)
    parser.add_argument(
        "--segment-rule",
        action="append",
        default=[],
        help="Example: '*.example.com=segment_upstream,chunk=512,delay=5'",
    )

    return parser


def make_settings(args: argparse.Namespace) -> Settings:
    default_policy = SegmentationPolicy(
        mode=args.segmentation,
        chunk_size=args.segment_chunk_size,
        delay_ms=args.segment_delay_ms,
    )
    rules = [parse_segment_rule(s) for s in args.segment_rule]

    return Settings(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        connect_timeout=args.connect_timeout,
        idle_timeout=args.idle_timeout,
        max_connections=args.max_connections,
        segmentation_default=default_policy,
        segmentation_rules=rules,
    )


def read_chunked_body(client_sock: socket.socket) -> bytes:
    """
    Read a chunked transfer-encoded body and return the raw bytes
    exactly as received (chunk sizes + CRLFs + trailers).

    Important: we must handle socket over-reads by buffering.
    """
    out = bytearray()
    buf = bytearray()

    def recv_more() -> bool:
        data = client_sock.recv(4096)
        if not data:
            return False
        buf.extend(data)
        return True

    def read_until(delim: bytes) -> bytes:
        while True:
            idx = buf.find(delim)
            if idx != -1:
                end = idx + len(delim)
                chunk = bytes(buf[:end])
                del buf[:end]
                return chunk
            if not recv_more():
                chunk = bytes(buf)
                buf.clear()
                return chunk

    def read_exact(n: int) -> bytes:
        while len(buf) < n:
            if not recv_more():
                break
        chunk = bytes(buf[:n])
        del buf[:n]
        return chunk

    while True:
        # Chunk-size line: "<hex>[;ext...]\r\n"
        line = read_until(b"\r\n")
        if not line:
            break

        out += line

        size_token = line.split(b";", 1)[0].strip()
        size_token = size_token.rstrip(b"\r\n")
        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise ValueError("Invalid chunk size") from exc

        if size == 0:
            # trailers end with blank line "\r\n"
            while True:
                trailer_line = read_until(b"\r\n")
                if not trailer_line:
                    break
                out += trailer_line
                if trailer_line == b"\r\n":
                    break
            break

        data_plus_crlf = read_exact(size + 2)
        if len(data_plus_crlf) < size + 2:
            raise ValueError("Incomplete chunk data")
        out += data_plus_crlf

    return bytes(out)


def read_request_body(
    client_sock: socket.socket,
    initial_body: bytes,
    headers: dict[str, str],
) -> bytes:
    """
    Read request body based on Transfer-Encoding or Content-Length.
    """
    transfer_encoding = headers.get("transfer-encoding")
    if transfer_encoding:
        te = transfer_encoding.lower()
        if te == "chunked":
            # v1 limitation: if initial_body contains bytes, we'd need to seed the chunk buffer.
            if initial_body:
                raise ValueError("Chunked body with buffered bytes not supported yet")
            return read_chunked_body(client_sock)

        if te != "identity":
            raise ValueError("Transfer-Encoding not supported")

    body = initial_body
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
        logging.info("[C%05d] %s %s from %s", cid, request.method, request.target, client_addr)

        try:
            body = read_request_body(client_sock, body_initial, request.headers)
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

    logging.info("Starting SegmentedProxy on %s:%d", settings.listen_host, settings.listen_port)

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
