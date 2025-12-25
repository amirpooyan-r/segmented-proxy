from __future__ import annotations

import socket
import threading
import time
from typing import Protocol

CACHE_TTL_SECONDS = 60


class Resolver(Protocol):
    def resolve(self, host: str, port: int) -> list[tuple[int, str]]:
        """
        Return a list of (address_family, ip) pairs.
        """
        ...


class SystemResolver:
    def resolve(self, host: str, port: int) -> list[tuple[int, str]]:
        infos = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        addrs: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()

        for family, _socktype, _proto, _canonname, sockaddr in infos:
            ip = sockaddr[0]
            key = (family, ip)
            if key in seen:
                continue
            seen.add(key)
            addrs.append(key)

        return addrs


class CachingResolver:
    def __init__(self, inner: Resolver, max_entries: int) -> None:
        self._inner = inner
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, int], tuple[float, tuple[tuple[int, str], ...]]] = {}

    def resolve(self, host: str, port: int) -> list[tuple[int, str]]:
        if self._max_entries <= 0:
            return self._inner.resolve(host, port)

        key = (host.lower(), port)
        now = time.monotonic()

        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                expires_at, addrs = entry
                if now < expires_at:
                    return list(addrs)
                del self._cache[key]

        addrs = self._inner.resolve(host, port)
        expires_at = now + CACHE_TTL_SECONDS

        with self._lock:
            if key not in self._cache and len(self._cache) >= self._max_entries:
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key, None)
            self._cache[key] = (expires_at, tuple(addrs))

        return list(addrs)
