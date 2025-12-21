from __future__ import annotations

import argparse
import itertools
import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.handlers import handle_connect_tunnel, handle_http_forward
from segmentedproxy.http import parse_http_request, send_http_error, split_headers_and_body
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


def _read_until_from_buffer(
    sock: socket.socket,
    buf: bytearray,
    delim: bytes,
    *,
    max_bytes: int = 1024 * 1024,
) -> bytes:
    """
    Read from sock until delim is found in buf. Return bytes up to and including the
    first delim occurrence, leaving any extra bytes in buf.
    """
    while True:
        idx = buf.find(delim)
        if idx != -1:
            end = idx + len(delim)
            out = bytes(buf[:end])
            del buf[:end]
            return out

        if len(buf) > max_bytes:
            raise ValueError("Read limit exceeded while waiting for delimiter")

        chunk = sock.recv(4096)
        if not chunk:
            # EOF
            return b""
        buf += chunk


def _read_exact_from_buffer(sock: socket.socket, buf: bytearray, n: int) -> bytes:
    """
    Read exactly n bytes, using buf first, then the socket.
    """
    while len(buf) < n:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk

    if len(buf) < n:
        raise ValueError("Incomplete data")

    out = bytes(buf[:n])
    del buf[:n]
    return out


def read_chunked_body(client_sock: socket.socket) -> bytes:
    """
    Read a chunked transfer-encoded body and return the raw bytes
    exactly as received (chunk sizes + CRLFs + trailers).

    Important: we must handle socket over-reads by buffering.

    Limitations:
    - Assumes chunk boundaries align with socket reads.
    - Does not support malformed or streaming chunk extensions.
    - Intended for forwarding, not reassembly or inspection.
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
        # Return bytes up to and including delim. Keep remainder in buf.
        while True:
            idx = buf.find(delim)
            if idx != -1:
                end = idx + len(delim)
                chunk = bytes(buf[:end])
                del buf[:end]
                return chunk
            if not recv_more():
                # EOF
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

        # Parse size (ignore extensions after ';')
        size_token = line.split(b";", 1)[0].strip()
        size_token = size_token.rstrip(b"\r\n")

        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise ValueError("Invalid chunk size") from exc

        if size == 0:
            # After 0-size chunk: read trailers, which end with a blank line "\r\n"
            while True:
                trailer_line = read_until(b"\r\n")
                if not trailer_line:
                    break
                out += trailer_line
                if trailer_line == b"\r\n":
                    break
            break

        # Chunk data + trailing CRLF
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
            # If we already buffered body bytes, we'd need a more complex parser.
            if initial_body:
                raise ValueError("Chunked body with buffered bytes not supported yet")
            return read_chunked_body(client_sock)

        if te != "identity":
            raise ValueError("Transfer-Encoding not supported")

    # Content-Length path
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
