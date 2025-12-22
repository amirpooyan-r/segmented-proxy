import pytest

from segmentedproxy.segmentation import (
    RequestContext,
    SegmentationEngine,
    SegmentationPolicy,
    match_policy,
    parse_segment_rule,
)


def test_default_strategy_is_none() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,chunk=512")
    assert rule.policy.strategy == "none"


def test_fixed_strategy_with_chunk() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,strategy=fixed,chunk=512")
    assert rule.policy.strategy == "fixed"
    assert rule.policy.chunk_size == 512


def test_none_strategy_ignores_chunk() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,strategy=none,chunk=512")
    assert rule.policy.strategy == "none"


def test_random_strategy_parses_min_max() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,strategy=random,min=256,max=2048")
    assert rule.policy.strategy == "random"
    assert rule.policy.min_chunk == 256
    assert rule.policy.max_chunk == 2048


@pytest.mark.parametrize(
    "text",
    [
        "*.a.com=segment_upstream,strategy=random,min=256",
        "*.a.com=segment_upstream,strategy=random,max=2048",
        "*.a.com=segment_upstream,strategy=random,min=2048,max=256",
        "*.a.com=segment_upstream,strategy=random,min=0,max=256",
        "*.a.com=segment_upstream,strategy=random,min=256,max=0",
    ],
)
def test_random_strategy_requires_min_max(text: str) -> None:
    with pytest.raises(ValueError):
        parse_segment_rule(text)


def test_match_policy_returns_first_match() -> None:
    rules = [
        parse_segment_rule("*.a.com=segment_upstream,chunk=512"),
        parse_segment_rule("*.a.com=segment_upstream,chunk=2048"),
    ]
    policy = match_policy("host.a.com", rules, SegmentationPolicy())
    assert policy.chunk_size == 512


def test_match_policy_returns_default_when_no_match() -> None:
    rules = [parse_segment_rule("*.b.com=segment_upstream,chunk=512")]
    default = SegmentationPolicy(mode="direct")
    policy = match_policy("host.a.com", rules, default)
    assert policy == default


def test_parse_action_block() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,action=block")
    assert rule.action == "block"


def test_parse_action_upstream() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,action=upstream,upstream=proxy.local:8080")
    assert rule.action == "upstream"
    assert rule.upstream == ("proxy.local", 8080)


def test_default_action_is_direct() -> None:
    rule = parse_segment_rule("*.a.com=segment_upstream,chunk=512")
    assert rule.action == "direct"


def test_engine_reports_matched_rule() -> None:
    rules = [parse_segment_rule("*.a.com=segment_upstream,chunk=512")]
    engine = SegmentationEngine(rules, SegmentationPolicy())
    ctx = RequestContext(method="GET", scheme="http", host="x.a.com", port=80, path="/")
    decision = engine.decide(ctx)
    assert decision.matched_rule is not None
    assert decision.matched_rule.host_glob == "*.a.com"


def test_engine_reports_default_when_no_match() -> None:
    rules = [parse_segment_rule("*.b.com=segment_upstream,chunk=512")]
    default = SegmentationPolicy(mode="direct")
    engine = SegmentationEngine(rules, default)
    ctx = RequestContext(method="GET", scheme="http", host="x.a.com", port=80, path="/")
    decision = engine.decide(ctx)
    assert decision.matched_rule is None
    assert decision.policy == default
    assert decision.action == "direct"


def test_engine_first_match_wins() -> None:
    rules = [
        parse_segment_rule("*.a.com=segment_upstream,chunk=512"),
        parse_segment_rule("*.a.com=segment_upstream,chunk=2048"),
    ]
    engine = SegmentationEngine(rules, SegmentationPolicy())
    ctx = RequestContext(method="GET", scheme="http", host="x.a.com", port=80, path="/")
    decision = engine.decide(ctx)
    assert decision.policy.chunk_size == 512


def test_engine_returns_action_and_upstream() -> None:
    rules = [
        parse_segment_rule("*.a.com=segment_upstream,action=upstream,upstream=proxy.local:8080")
    ]
    engine = SegmentationEngine(rules, SegmentationPolicy())
    ctx = RequestContext(method="GET", scheme="http", host="x.a.com", port=80, path="/")
    decision = engine.decide(ctx)
    assert decision.action == "upstream"
    assert decision.upstream == ("proxy.local", 8080)
