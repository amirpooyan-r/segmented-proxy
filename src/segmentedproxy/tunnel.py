from __future__ import annotations

import logging
import select
import socket
import time


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


def open_upstream(
    host: str, port: int, connect_timeout: float, idle_timeout: float
) -> socket.socket:
    upstream = socket.create_connection((host, port), timeout=connect_timeout)
    upstream.settimeout(idle_timeout)
    return upstream
