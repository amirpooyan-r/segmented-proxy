from __future__ import annotations

import random
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Protocol

FIXED_SYSTEM_TTL = 60
MIN_TTL = 5
MAX_TTL = 3600
DNS_TIMEOUT_SECONDS = 2.0

A_RECORD = 1
AAAA_RECORD = 28


@dataclass(frozen=True)
class ResolveResult:
    addrs: list[tuple[int, str]]
    ttl_seconds: int


class Resolver(Protocol):
    def resolve(self, host: str, port: int) -> ResolveResult:
        """
        Return addresses and a per-query TTL for caching.
        """
        ...


class SystemResolver:
    def resolve(self, host: str, port: int) -> ResolveResult:
        infos = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        addrs: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()

        for family, _socktype, _proto, _canonname, sockaddr in infos:
            ip = sockaddr[0]
            key = (family, ip)
            if key in seen:
                continue
            seen.add(key)
            addrs.append(key)

        return ResolveResult(addrs=addrs, ttl_seconds=FIXED_SYSTEM_TTL)


class PlainDnsResolver:
    def __init__(self, server_ip: str) -> None:
        self._server_ip = server_ip
        self._family = socket.AF_INET6 if ":" in server_ip else socket.AF_INET

    def resolve(self, host: str, port: int) -> ResolveResult:
        addrs: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()
        ttl_values: list[int] = []

        for qtype, family in ((A_RECORD, socket.AF_INET), (AAAA_RECORD, socket.AF_INET6)):
            response_addrs, ttl_seconds = self._query(host, qtype)
            if response_addrs:
                ttl_values.append(ttl_seconds)
            for addr in response_addrs:
                key = (family, addr)
                if key in seen:
                    continue
                seen.add(key)
                addrs.append(key)

        if not addrs:
            raise ValueError(f"No DNS answers for {host}")

        ttl_min = min(ttl_values) if ttl_values else 0
        return ResolveResult(addrs=addrs, ttl_seconds=ttl_min)

    def _query(self, host: str, qtype: int) -> tuple[list[str], int]:
        txid = random.getrandbits(16)
        query = self._build_query(host, qtype, txid)

        with socket.socket(self._family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(DNS_TIMEOUT_SECONDS)
            sock.sendto(query, (self._server_ip, 53))
            data, _addr = sock.recvfrom(4096)

        if len(data) < 12:
            raise ValueError("DNS response too short")
        resp_id = struct.unpack("!H", data[:2])[0]
        if resp_id != txid:
            raise ValueError("DNS response transaction ID mismatch")

        return self._parse_response(data, qtype)

    @staticmethod
    def _build_query(host: str, qtype: int, txid: int) -> bytes:
        flags = 0x0100  # RD=1
        header = struct.pack("!HHHHHH", txid, flags, 1, 0, 0, 0)
        qname = PlainDnsResolver._encode_name(host)
        question = qname + struct.pack("!HH", qtype, 1)
        return header + question

    @staticmethod
    def _encode_name(host: str) -> bytes:
        parts = host.rstrip(".").split(".")
        out = bytearray()
        for part in parts:
            if not part or len(part) > 63:
                raise ValueError("Invalid DNS name")
            out.append(len(part))
            out.extend(part.encode("ascii"))
        out.append(0)
        return bytes(out)

    @staticmethod
    def _parse_response(data: bytes, qtype: int) -> tuple[list[str], int]:
        if len(data) < 12:
            raise ValueError("DNS response too short")
        _txid, _flags, qdcount, ancount, _nscount, _arcount = struct.unpack("!HHHHHH", data[:12])
        offset = 12

        for _ in range(qdcount):
            _name, offset = PlainDnsResolver._read_name(data, offset)
            if offset + 4 > len(data):
                raise ValueError("DNS response truncated in question")
            offset += 4

        addrs: list[str] = []
        ttl_min: int | None = None

        for _ in range(ancount):
            _name, offset = PlainDnsResolver._read_name(data, offset)
            if offset + 10 > len(data):
                raise ValueError("DNS response truncated in answer")
            rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
            offset += 10
            if offset + rdlength > len(data):
                raise ValueError("DNS response truncated in rdata")
            rdata = data[offset : offset + rdlength]
            offset += rdlength

            if rclass != 1 or rtype != qtype:
                continue
            if rtype == A_RECORD and rdlength == 4:
                addrs.append(socket.inet_ntop(socket.AF_INET, rdata))
            elif rtype == AAAA_RECORD and rdlength == 16:
                addrs.append(socket.inet_ntop(socket.AF_INET6, rdata))
            else:
                continue

            ttl_min = ttl if ttl_min is None else min(ttl_min, ttl)

        return addrs, ttl_min or 0

    @staticmethod
    def _read_name(data: bytes, offset: int) -> tuple[str, int]:
        labels: list[str] = []
        jumped = False
        next_offset = offset
        after_pointer = offset
        seen_offsets: set[int] = set()

        while True:
            if next_offset >= len(data):
                raise ValueError("DNS name out of range")
            length = data[next_offset]
            if length & 0xC0 == 0xC0:
                if next_offset + 1 >= len(data):
                    raise ValueError("DNS name pointer truncated")
                pointer = ((length & 0x3F) << 8) | data[next_offset + 1]
                if pointer in seen_offsets:
                    raise ValueError("DNS name pointer loop")
                seen_offsets.add(pointer)
                if not jumped:
                    after_pointer = next_offset + 2
                    jumped = True
                next_offset = pointer
                continue
            if length == 0:
                next_offset += 1
                break
            next_offset += 1
            if next_offset + length > len(data):
                raise ValueError("DNS label out of range")
            labels.append(data[next_offset : next_offset + length].decode("ascii"))
            next_offset += length

        name = ".".join(labels)
        return name, after_pointer if jumped else next_offset


class CachingResolver:
    def __init__(self, inner: Resolver, max_entries: int) -> None:
        self._inner = inner
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, int], tuple[float, tuple[tuple[int, str], ...]]] = {}

    def resolve(self, host: str, port: int) -> ResolveResult:
        if self._max_entries <= 0:
            return self._inner.resolve(host, port)

        key = (host.lower(), port)
        now = time.monotonic()

        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                expires_at, addrs = entry
                if now < expires_at:
                    return ResolveResult(addrs=list(addrs), ttl_seconds=int(expires_at - now))
                del self._cache[key]

        result = self._inner.resolve(host, port)
        ttl_seconds = result.ttl_seconds
        if ttl_seconds > 0:
            ttl_seconds = max(MIN_TTL, min(ttl_seconds, MAX_TTL))
        if ttl_seconds <= 0:
            return result
        expires_at = now + ttl_seconds

        with self._lock:
            if key not in self._cache and len(self._cache) >= self._max_entries:
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key, None)
            self._cache[key] = (expires_at, tuple(result.addrs))

        return result
