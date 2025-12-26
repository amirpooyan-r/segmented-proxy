from __future__ import annotations

import socket

from segmentedproxy.resolver import CachingResolver, ResolveResult


class FakeResolver:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.calls = 0
        self._ttl_seconds = ttl_seconds

    def resolve(self, host: str, port: int) -> ResolveResult:
        self.calls += 1
        return ResolveResult(
            addrs=[(socket.AF_INET, "203.0.113.10")],
            ttl_seconds=self._ttl_seconds,
        )


def test_cache_hit() -> None:
    fake = FakeResolver()
    resolver = CachingResolver(fake, max_entries=2)

    resolver.resolve("example.com", 80)
    resolver.resolve("example.com", 80)

    assert fake.calls == 1


def test_cache_expiry(monkeypatch) -> None:
    fake = FakeResolver(ttl_seconds=10)
    resolver = CachingResolver(fake, max_entries=2)
    now = 0.0

    def fake_monotonic() -> float:
        return now

    monkeypatch.setattr("segmentedproxy.resolver.time.monotonic", fake_monotonic)

    resolver.resolve("example.com", 80)
    now += 11
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
