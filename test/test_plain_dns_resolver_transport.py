from __future__ import annotations

import socket
import struct

from segmentedproxy.resolver import A_RECORD, PlainDnsResolver


def _build_response(txid: int, qtype: int, ttl: int, *, truncated: bool = False) -> bytes:
    flags = 0x8180 | (0x0200 if truncated else 0)
    header = struct.pack("!HHHHHH", txid, flags, 1, 1, 0, 0)
    qname = b"\x07example\x03com\x00"
    question = qname + struct.pack("!HH", qtype, 1)
    if qtype == A_RECORD:
        rdata = socket.inet_pton(socket.AF_INET, "93.184.216.34")
    else:
        rdata = socket.inet_pton(socket.AF_INET6, "2606:2800:220:1:248:1893:25c8:1946")
    answer = b"\xc0\x0c" + struct.pack("!HHIH", qtype, 1, ttl, len(rdata)) + rdata
    return header + question + answer


def _response_for_query(query: bytes, *, truncated: bool = False) -> bytes:
    txid = struct.unpack("!H", query[:2])[0]
    qtype = struct.unpack("!H", query[-4:-2])[0]
    return _build_response(txid, qtype, 120, truncated=truncated)


def test_transport_udp_success_no_tcp() -> None:
    resolver = PlainDnsResolver("1.1.1.1")
    calls: list[str] = []

    def fake_udp(query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("udp")
        return _response_for_query(query)

    def fake_tcp(_query: bytes, _port: int) -> bytes:
        raise AssertionError("TCP should not be called")

    resolver._query_udp = fake_udp  # type: ignore[assignment]
    resolver._query_tcp = fake_tcp  # type: ignore[assignment]

    result = resolver.resolve("example.com", 80)

    assert result.addrs
    assert calls.count("udp") == 2


def test_transport_udp_fallback_on_error() -> None:
    resolver = PlainDnsResolver("1.1.1.1")
    calls: list[str] = []

    def fake_udp(_query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("udp")
        raise TimeoutError("udp timeout")

    def fake_tcp(query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("tcp")
        return _response_for_query(query)

    resolver._query_udp = fake_udp  # type: ignore[assignment]
    resolver._query_tcp = fake_tcp  # type: ignore[assignment]

    result = resolver.resolve("example.com", 80)

    assert result.addrs
    assert calls.count("udp") == 2
    assert calls.count("tcp") == 2


def test_transport_udp_fallback_on_truncated() -> None:
    resolver = PlainDnsResolver("1.1.1.1")
    calls: list[str] = []

    def fake_udp(query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("udp")
        return _response_for_query(query, truncated=True)

    def fake_tcp(query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("tcp")
        return _response_for_query(query)

    resolver._query_udp = fake_udp  # type: ignore[assignment]
    resolver._query_tcp = fake_tcp  # type: ignore[assignment]

    result = resolver.resolve("example.com", 80)

    assert result.addrs
    assert calls.count("udp") == 2
    assert calls.count("tcp") == 2


def test_transport_tcp_only() -> None:
    resolver = PlainDnsResolver("1.1.1.1", transport="tcp")
    calls: list[str] = []

    def fake_udp(_query: bytes, _port: int) -> bytes:
        raise AssertionError("UDP should not be called")

    def fake_tcp(query: bytes, port: int) -> bytes:
        assert port == 53
        calls.append("tcp")
        return _response_for_query(query)

    resolver._query_udp = fake_udp  # type: ignore[assignment]
    resolver._query_tcp = fake_tcp  # type: ignore[assignment]

    result = resolver.resolve("example.com", 80)

    assert result.addrs
    assert calls.count("tcp") == 2


def test_dns_port_passed_to_queries() -> None:
    resolver = PlainDnsResolver("1.1.1.1", dns_port=5353)
    seen_ports: list[int] = []

    def fake_udp(query: bytes, port: int) -> bytes:
        seen_ports.append(port)
        return _response_for_query(query)

    resolver._query_udp = fake_udp  # type: ignore[assignment]

    result = resolver.resolve("example.com", 80)

    assert result.addrs
    assert seen_ports == [5353, 5353]
