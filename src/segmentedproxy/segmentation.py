from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class SegmentationPolicy:
    # v1 modes:
    # - "direct": normal CONNECT tunnel relay
    # - "segment_upstream": segment only client->upstream direction in CONNECT tunnel
    mode: str = "direct"
    chunk_size: int = 1024
    delay_ms: int = 0


@dataclass(frozen=True)
class SegmentationRule:
    host_glob: str
    policy: SegmentationPolicy


def match_policy(
    host: str, rules: Iterable[SegmentationRule], default: SegmentationPolicy
) -> SegmentationPolicy:
    for rule in rules:
        if fnmatch(host, rule.host_glob):
            return rule.policy
    return default


def parse_segment_rule(text: str) -> SegmentationRule:
    """
    Format:
      "<host_glob>=<mode>[,chunk=<int>][,delay=<int>]"
    Example:
      "*.example.com=segment_upstream,chunk=512,delay=5"
    """
    if "=" not in text:
        raise ValueError(
            "segment rule must contain '=' "
            "(example: '*.example.com=segment_upstream,chunk=512,delay=5')"
        )

    host_glob, rhs = text.split("=", 1)
    host_glob = host_glob.strip()
    rhs = rhs.strip()

    parts = [p.strip() for p in rhs.split(",") if p.strip()]
    if not parts:
        raise ValueError("segment rule missing mode")

    mode = parts[0]
    chunk_size = 1024
    delay_ms = 0

    for p in parts[1:]:
        if "=" not in p:
            raise ValueError(f"invalid rule token '{p}', expected key=value")
        k, v = p.split("=", 1)
        k = k.strip().lower()
        v = v.strip()

        if k == "chunk":
            chunk_size = int(v)
        elif k == "delay":
            delay_ms = int(v)
        else:
            raise ValueError(f"unknown rule key '{k}'")

    return SegmentationRule(
        host_glob=host_glob,
        policy=SegmentationPolicy(mode=mode, chunk_size=chunk_size, delay_ms=delay_ms),
    )
