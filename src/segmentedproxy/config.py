from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    listen_host: str = "127.0.0.1"
    listen_port: int = 8080
    connect_timeout: float = 10.0
    idle_timeout: float = 60.0
    max_connections: int = 200

    # Policy / segmentation rules
    allow_domains: tuple[str, ...] = field(default_factory=tuple)
    deny_domains: tuple[str, ...] = field(default_factory=tuple)
    deny_private: bool = True
