from __future__ import annotations

import logging
import random
import select
import socket
import threading
import time

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


def open_upstream(
    host: str, port: int, connect_timeout: float, idle_timeout: float
) -> socket.socket:
    upstream = socket.create_connection((host, port), timeout=connect_timeout)
    upstream.settimeout(idle_timeout)
    return upstream
