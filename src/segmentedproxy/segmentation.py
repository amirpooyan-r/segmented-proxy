from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Literal, cast

Action = Literal["direct", "upstream", "block"]


@dataclass(frozen=True)
class SegmentationPolicy:
    # v1 modes:
    # - "direct": normal CONNECT tunnel relay
    # - "segment_upstream": segment only client->upstream direction in CONNECT tunnel
    mode: str = "direct"
    strategy: str = "none"
    chunk_size: int = 1024
    delay_ms: int = 0
    min_chunk: int | None = None
    max_chunk: int | None = None


@dataclass(frozen=True)
class SegmentationRule:
    host_glob: str
    policy: SegmentationPolicy
    action: Action = "direct"
    upstream: tuple[str, int] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class RequestContext:
    method: str
    scheme: str
    host: str
    port: int
    path: str = ""


@dataclass(frozen=True)
class SegmentationDecision:
    action: Action
    policy: SegmentationPolicy
    upstream: tuple[str, int] | None = None
    matched_rule: SegmentationRule | None = None
    reason: str | None = None


class SegmentationEngine:
    def __init__(self, rules: Iterable[SegmentationRule], default: SegmentationPolicy) -> None:
        self._rules = list(rules)
        self._default = default

    def decide(self, ctx: RequestContext) -> SegmentationDecision:
        for rule in self._rules:
            if fnmatch(ctx.host, rule.host_glob):
                return SegmentationDecision(
                    action=rule.action,
                    policy=rule.policy,
                    upstream=rule.upstream,
                    matched_rule=rule,
                    reason=rule.reason,
                )
        return SegmentationDecision(
            action="direct",
            policy=self._default,
            upstream=None,
            matched_rule=None,
            reason=None,
        )


def match_policy(
    host: str, rules: Iterable[SegmentationRule], default: SegmentationPolicy
) -> SegmentationPolicy:
    engine = SegmentationEngine(rules, default)
    decision = engine.decide(RequestContext(method="", scheme="", host=host, port=0, path=""))
    return decision.policy


def parse_segment_rule(text: str) -> SegmentationRule:
    """
    Format:
      "<host_glob>=<mode>[,strategy=none|fixed|random][,chunk=<int>]"
      "[,min=<int>][,max=<int>][,delay=<int>]"
      "[,action=direct|upstream|block][,upstream=HOST:PORT][,reason=<text>]"
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
    strategy = "none"
    chunk_size = 1024
    delay_ms = 0
    min_chunk: int | None = None
    max_chunk: int | None = None
    action: Action = "direct"
    upstream: tuple[str, int] | None = None
    reason: str | None = None

    for p in parts[1:]:
        if "=" not in p:
            raise ValueError(f"invalid rule token '{p}', expected key=value")
        k, v = p.split("=", 1)
        k = k.strip().lower()
        v = v.strip()

        if k == "strategy":
            strategy = v.lower()
        elif k == "chunk":
            chunk_size = _parse_int(v, "chunk")
        elif k in {"min", "chunk_min"}:
            min_chunk = _parse_int(v, k)
        elif k in {"max", "chunk_max"}:
            max_chunk = _parse_int(v, k)
        elif k == "delay":
            delay_ms = _parse_int(v, "delay")
        elif k == "action":
            action = _parse_action(v)
        elif k == "upstream":
            upstream = _parse_upstream(v)
        elif k == "reason":
            reason = v
        else:
            raise ValueError(f"unknown rule key '{k}'")

    _validate_policy(strategy, chunk_size, min_chunk, max_chunk)
    _validate_action(action, upstream)

    return SegmentationRule(
        host_glob=host_glob,
        policy=SegmentationPolicy(
            mode=mode,
            strategy=strategy,
            chunk_size=chunk_size,
            delay_ms=delay_ms,
            min_chunk=min_chunk,
            max_chunk=max_chunk,
        ),
        action=action,
        upstream=upstream,
        reason=reason,
    )


def _parse_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"invalid int for '{label}': '{value}'") from exc


def _validate_policy(
    strategy: str, chunk_size: int, min_chunk: int | None, max_chunk: int | None
) -> None:
    if strategy not in {"none", "fixed", "random"}:
        raise ValueError(f"unknown strategy '{strategy}'")
    if strategy == "fixed":
        if chunk_size <= 0:
            raise ValueError("fixed strategy requires chunk > 0")
    elif strategy == "random":
        if min_chunk is None or max_chunk is None:
            raise ValueError("random strategy requires both min and max")
        if min_chunk <= 0 or max_chunk <= 0:
            raise ValueError("random strategy requires min/max > 0")
        if min_chunk > max_chunk:
            raise ValueError("random strategy requires min <= max")


def _parse_action(value: str) -> Action:
    action = value.strip().lower()
    if action not in {"direct", "upstream", "block"}:
        raise ValueError(f"unknown action '{value}'")
    return cast(Action, action)


def _parse_upstream(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise ValueError("upstream must be host:port")
    host, port_s = value.rsplit(":", 1)
    host = host.strip()
    if not host:
        raise ValueError("upstream must include host")
    try:
        port = int(port_s)
    except ValueError as exc:
        raise ValueError(f"invalid upstream port '{port_s}'") from exc
    return host, port


def _validate_action(action: Action, upstream: tuple[str, int] | None) -> None:
    if action == "upstream" and upstream is None:
        raise ValueError("upstream action requires upstream=HOST:PORT")
    if action == "block" and upstream is not None:
        raise ValueError("block action cannot include upstream")
