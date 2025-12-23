import random

from segmentedproxy.handlers import _send_body_with_policy
from segmentedproxy.segmentation import SegmentationPolicy


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)


def test_send_body_fixed_segmentation() -> None:
    sock = FakeSocket()
    policy = SegmentationPolicy(mode="segment_upstream", strategy="fixed", chunk_size=3)
    _send_body_with_policy(sock, b"abcdefgh", policy)
    assert sock.sent == [b"abc", b"def", b"gh"]


def test_send_body_random_segmentation(monkeypatch) -> None:
    sock = FakeSocket()
    policy = SegmentationPolicy(
        mode="segment_upstream",
        strategy="random",
        min_chunk=2,
        max_chunk=4,
    )
    monkeypatch.setattr(random, "randint", lambda _a, _b: 2)
    _send_body_with_policy(sock, b"abcdef", policy)
    assert sock.sent == [b"ab", b"cd", b"ef"]


def test_send_body_random_falls_back_to_fixed() -> None:
    sock = FakeSocket()
    policy = SegmentationPolicy(
        mode="segment_upstream",
        strategy="random",
        chunk_size=3,
    )
    _send_body_with_policy(sock, b"abcdefgh", policy)
    assert sock.sent == [b"abc", b"def", b"gh"]


def test_send_body_strategy_none() -> None:
    sock = FakeSocket()
    policy = SegmentationPolicy(mode="segment_upstream", strategy="none")
    _send_body_with_policy(sock, b"abcdef", policy)
    assert sock.sent == [b"abcdef"]
