from __future__ import annotations

import logging
import random
import select
import socket
import threading
import time

from segmentedproxy.resolver import Resolver
from segmentedproxy.segmentation import SegmentationPolicy


def parse_connect_target(target: str) -> tuple[str, int]:
    """
    CONNECT target is host:port
    """
    if ":" not in target:
        raise ValueError("CONNECT target must be host:port")
    host, port_s = target.rsplit(":", 1)
    port = int(port_s)
    return host, port


def relay_bidirectional(
    a: socket.socket,
    b: socket.socket,
    idle_timeout: float,
) -> None:
    """
    Relay data between sockets a <-> b using select().
    Ends when either side closes or idle_timeout passes.
    """
    a.setblocking(False)
    b.setblocking(False)

    last_activity = time.monotonic()
    sockets = [a, b]

    while True:
        if time.monotonic() - last_activity > idle_timeout:
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


def _relay_oneway(
    src: socket.socket, dst: socket.socket, idle_timeout: float, stop: threading.Event
) -> None:
    """
    Simple one-way relay: src -> dst. Stops on close/error/stop.
    Uses blocking recv with timeout for simplicity.
    """
    src.settimeout(idle_timeout)
    dst.settimeout(idle_timeout)

    while not stop.is_set():
        try:
            data = src.recv(4096)
        except TimeoutError:
            continue
        except OSError:
            return

        if not data:
            return

        try:
            dst.sendall(data)
        except OSError:
            return


def relay_client_to_upstream_segmented(
    client: socket.socket,
    upstream: socket.socket,
    *,
    chunk_size: int,
    delay_ms: int,
    idle_timeout: float,
    stop: threading.Event,
) -> None:
    """
    Segmented relay: client -> upstream.
    Reads from client and sends to upstream in small chunks with optional delay.
    """
    client.settimeout(idle_timeout)
    upstream.settimeout(idle_timeout)

    if chunk_size <= 0:
        chunk_size = 1024

    while not stop.is_set():
        try:
            data = client.recv(4096)
        except TimeoutError:
            continue
        except OSError:
            return

        if not data:
            return

        for i in range(0, len(data), chunk_size):
            part = data[i : i + chunk_size]
            try:
                upstream.sendall(part)
            except OSError:
                return
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)


def relay_client_to_upstream_random_segmented(
    client: socket.socket,
    upstream: socket.socket,
    *,
    min_chunk: int,
    max_chunk: int,
    delay_ms: int,
    idle_timeout: float,
    stop: threading.Event,
) -> None:
    """
    Segmented relay: client -> upstream with random chunk sizes.
    """
    client.settimeout(idle_timeout)
    upstream.settimeout(idle_timeout)

    if min_chunk <= 0 or max_chunk <= 0 or min_chunk > max_chunk:
        return

    while not stop.is_set():
        try:
            data = client.recv(4096)
        except TimeoutError:
            continue
        except OSError:
            return

        if not data:
            return

        idx = 0
        data_len = len(data)
        while idx < data_len:
            chunk_size = random.randint(min_chunk, max_chunk)
            part = data[idx : idx + chunk_size]
            idx += chunk_size
            try:
                upstream.sendall(part)
            except OSError:
                return
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)


def relay_tunnel(
    client: socket.socket,
    upstream: socket.socket,
    *,
    idle_timeout: float,
    policy: SegmentationPolicy,
) -> None:
    """
    Apply segmentation policy to a CONNECT tunnel.

    v1:
    - direct: use relay_bidirectional
    - segment_upstream: segment only client->upstream direction, upstream->client is direct
    """
    if policy.mode == "direct":
        relay_bidirectional(client, upstream, idle_timeout=idle_timeout)
        return

    if policy.mode != "segment_upstream":
        logging.debug("Unknown segmentation mode '%s', falling back to direct", policy.mode)
        relay_bidirectional(client, upstream, idle_timeout=idle_timeout)
        return

    if policy.strategy == "none":
        relay_bidirectional(client, upstream, idle_timeout=idle_timeout)
        return

    stop = threading.Event()

    # upstream -> client (direct)
    t = threading.Thread(
        target=_relay_oneway,
        args=(upstream, client, idle_timeout, stop),
        daemon=True,
    )
    t.start()

    try:
        # client -> upstream (segmented)
        if policy.strategy == "fixed":
            relay_client_to_upstream_segmented(
                client,
                upstream,
                chunk_size=policy.chunk_size,
                delay_ms=policy.delay_ms,
                idle_timeout=idle_timeout,
                stop=stop,
            )
        elif policy.strategy == "random":
            if policy.min_chunk is None or policy.max_chunk is None:
                relay_client_to_upstream_segmented(
                    client,
                    upstream,
                    chunk_size=policy.chunk_size,
                    delay_ms=policy.delay_ms,
                    idle_timeout=idle_timeout,
                    stop=stop,
                )
            else:
                relay_client_to_upstream_random_segmented(
                    client,
                    upstream,
                    min_chunk=policy.min_chunk,
                    max_chunk=policy.max_chunk,
                    delay_ms=policy.delay_ms,
                    idle_timeout=idle_timeout,
                    stop=stop,
                )
        else:
            relay_client_to_upstream_segmented(
                client,
                upstream,
                chunk_size=policy.chunk_size,
                delay_ms=policy.delay_ms,
                idle_timeout=idle_timeout,
                stop=stop,
            )
    finally:
        stop.set()
        t.join(timeout=1.0)


def perform_upstream_connect(
    upstream: socket.socket,
    target_host: str,
    target_port: int,
    *,
    idle_timeout: float,
) -> bool:
    """
    Establish a CONNECT tunnel through an upstream HTTP proxy.
    """
    request = (
        f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
        f"Host: {target_host}:{target_port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("iso-8859-1")

    upstream.settimeout(idle_timeout)
    upstream.sendall(request)

    response = _recv_headers(upstream)
    if not response:
        return False

    status_line = response.split(b"\r\n", 1)[0]
    try:
        status_text = status_line.decode("iso-8859-1", errors="replace")
    except ValueError:
        return False

    parts = status_text.split(" ", 2)
    if len(parts) < 2:
        return False
    try:
        code = int(parts[1])
    except ValueError:
        return False
    return code == 200


def _recv_headers(sock: socket.socket, *, max_bytes: int = 65536) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        try:
            chunk = sock.recv(4096)
        except TimeoutError:
            return b""
        except OSError:
            return b""
        if not chunk:
            break
        data += chunk
        if len(data) > max_bytes:
            break
    return data


def open_upstream(
    host: str,
    port: int,
    connect_timeout: float,
    idle_timeout: float,
    resolver: Resolver,
) -> socket.socket:
    last_error: OSError | None = None
    addrs = resolver.resolve(host, port)

    for family, ip in addrs:
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.settimeout(connect_timeout)
            sock.connect((ip, port))
            sock.settimeout(idle_timeout)
            return sock
        except OSError as exc:
            last_error = exc
            try:
                sock.close()
            except Exception:
                pass

    if last_error is not None:
        raise last_error
    raise OSError("No addresses resolved for connection")
