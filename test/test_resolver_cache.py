from __future__ import annotations

import socket

from segmentedproxy.resolver import CACHE_TTL_SECONDS, CachingResolver


class FakeResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, host: str, port: int) -> list[tuple[int, str]]:
        self.calls += 1
        return [(socket.AF_INET, "203.0.113.10")]


def test_cache_hit() -> None:
    fake = FakeResolver()
    resolver = CachingResolver(fake, max_entries=2)

    resolver.resolve("example.com", 80)
    resolver.resolve("example.com", 80)

    assert fake.calls == 1


def test_cache_expiry(monkeypatch) -> None:
    fake = FakeResolver()
    resolver = CachingResolver(fake, max_entries=2)
    now = 0.0

    def fake_monotonic() -> float:
        return now

    monkeypatch.setattr("segmentedproxy.resolver.time.monotonic", fake_monotonic)

    resolver.resolve("example.com", 80)
    now += CACHE_TTL_SECONDS + 1
    resolver.resolve("example.com", 80)

    assert fake.calls == 2


def test_cache_disabled() -> None:
    fake = FakeResolver()
    resolver = CachingResolver(fake, max_entries=0)

    resolver.resolve("example.com", 80)
    resolver.resolve("example.com", 80)

    assert fake.calls == 2


def test_cache_eviction_fifo() -> None:
    fake = FakeResolver()
    resolver = CachingResolver(fake, max_entries=2)

    resolver.resolve("a.example", 80)
    resolver.resolve("b.example", 80)
    resolver.resolve("c.example", 80)
    resolver.resolve("a.example", 80)

    assert fake.calls == 4
