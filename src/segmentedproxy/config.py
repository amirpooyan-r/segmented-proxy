from __future__ import annotations

from dataclasses import dataclass, field

from segmentedproxy.resolver import Resolver, SystemResolver
from segmentedproxy.segmentation import SegmentationPolicy, SegmentationRule


@dataclass(frozen=True)
class Settings:
    listen_host: str = "127.0.0.1"
    listen_port: int = 8080
    connect_timeout: float = 10.0
    idle_timeout: float = 60.0
    max_connections: int = 200
    dns_cache_size: int = 0
    dns_server: str | None = None
    dns_port: int = 53
    dns_transport: str = "udp"
    resolver: Resolver = field(default_factory=SystemResolver)

    def __post_init__(self) -> None:
        if self.dns_cache_size < 0:
            raise ValueError("dns_cache_size must be >= 0")
        if not 1 <= self.dns_port <= 65535:
            raise ValueError("dns_port must be between 1 and 65535")
        if self.dns_transport not in {"udp", "tcp"}:
            raise ValueError("dns_transport must be udp or tcp")

    # Policy / segmentation rules
    allow_domains: tuple[str, ...] = field(default_factory=tuple)
    deny_domains: tuple[str, ...] = field(default_factory=tuple)
    deny_private: bool = True

    # Segmentation (CONNECT tunnel behavior)
    segmentation_default: SegmentationPolicy = SegmentationPolicy()
    segmentation_rules: list[SegmentationRule] = field(default_factory=list)
