import pytest

from segmentedproxy.segmentation import (
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
