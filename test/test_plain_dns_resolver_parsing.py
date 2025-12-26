from __future__ import annotations

import socket
import struct

from segmentedproxy.resolver import A_RECORD, AAAA_RECORD, PlainDnsResolver


def _build_response(qtype: int, ttl: int, rdata: bytes, *, flags: int = 0x8180) -> bytes:
    txid = 0x1A2B
    header = struct.pack("!HHHHHH", txid, flags, 1, 1, 0, 0)
    qname = b"\x07example\x03com\x00"
    question = qname + struct.pack("!HH", qtype, 1)
    answer = b"\xc0\x0c" + struct.pack("!HHIH", qtype, 1, ttl, len(rdata)) + rdata
    return header + question + answer


def test_parse_a_record() -> None:
    rdata = socket.inet_pton(socket.AF_INET, "93.184.216.34")
    data = _build_response(A_RECORD, 120, rdata)

    addrs, ttl, truncated = PlainDnsResolver._parse_response(data, A_RECORD)

    assert addrs == ["93.184.216.34"]
    assert ttl == 120
    assert truncated is False


def test_parse_aaaa_record() -> None:
    rdata = socket.inet_pton(socket.AF_INET6, "2606:2800:220:1:248:1893:25c8:1946")
    data = _build_response(AAAA_RECORD, 300, rdata)

    addrs, ttl, truncated = PlainDnsResolver._parse_response(data, AAAA_RECORD)

    assert addrs == ["2606:2800:220:1:248:1893:25c8:1946"]
    assert ttl == 300
    assert truncated is False


def test_parse_truncated_flag() -> None:
    rdata = socket.inet_pton(socket.AF_INET, "93.184.216.34")
    data = _build_response(A_RECORD, 120, rdata, flags=0x8380)

    addrs, ttl, truncated = PlainDnsResolver._parse_response(data, A_RECORD)

    assert addrs == ["93.184.216.34"]
    assert ttl == 120
    assert truncated is True
