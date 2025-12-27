from __future__ import annotations

import logging
import random
import socket
import struct
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

FIXED_SYSTEM_TTL = 60
MIN_TTL = 5
MAX_TTL = 3600
DNS_TIMEOUT_SECONDS = 2.0

A_RECORD = 1
AAAA_RECORD = 28

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolveResult:
    addrs: list[tuple[int, str]]
    ttl_seconds: int


@dataclass(frozen=True)
class DnsTrace:
    dns: str
    cache: str
    transport: str
    fallback: int


class _DnsTraceContext:
    def __init__(self) -> None:
        self._local = threading.local()

    def set(self, trace: DnsTrace) -> None:
        self._local.trace = trace

    def get(self) -> DnsTrace | None:
        return getattr(self._local, "trace", None)

    def clear(self) -> None:
        if hasattr(self._local, "trace"):
            delattr(self._local, "trace")


_dns_trace_ctx = _DnsTraceContext()


def set_dns_trace(trace: DnsTrace) -> None:
    _dns_trace_ctx.set(trace)


def get_dns_trace() -> DnsTrace | None:
    return _dns_trace_ctx.get()


def clear_dns_trace() -> None:
    _dns_trace_ctx.clear()


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

        set_dns_trace(DnsTrace(dns="system", cache="miss", transport="udp", fallback=0))
        return ResolveResult(addrs=addrs, ttl_seconds=FIXED_SYSTEM_TTL)


class PlainDnsResolver:
    def __init__(
        self,
        server_ip: str,
        dns_port: int = 53,
        transport: str = "udp",
        timeout_seconds: float = DNS_TIMEOUT_SECONDS,
    ) -> None:
        if not 1 <= dns_port <= 65535:
            raise ValueError("dns_port must be between 1 and 65535")
        if transport not in {"udp", "tcp"}:
            raise ValueError("transport must be 'udp' or 'tcp'")
        self._server_ip = server_ip
        self._dns_port = dns_port
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._family = socket.AF_INET6 if ":" in server_ip else socket.AF_INET

    def resolve(self, host: str, port: int) -> ResolveResult:
        addrs: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()
        ttl_values: list[int] = []
        transport_used = self._transport
        fallback_used = 0

        for qtype, family in ((A_RECORD, socket.AF_INET), (AAAA_RECORD, socket.AF_INET6)):
            response_addrs, ttl_seconds, transport, fallback = self._resolve_type(host, port, qtype)
            if response_addrs:
                ttl_values.append(ttl_seconds)
            for addr in response_addrs:
                key = (family, addr)
                if key in seen:
                    continue
                seen.add(key)
                addrs.append(key)
            if transport == "tcp":
                transport_used = "tcp"
            if fallback:
                fallback_used = 1

        if not addrs:
            raise ValueError(f"No DNS answers for {host}")

        ttl_min = min(ttl_values) if ttl_values else 0
        set_dns_trace(
            DnsTrace(
                dns="custom",
                cache="miss",
                transport=transport_used,
                fallback=fallback_used,
            )
        )
        return ResolveResult(addrs=addrs, ttl_seconds=ttl_min)

    def _resolve_type(self, host: str, port: int, qtype: int) -> tuple[list[str], int, str, int]:
        txid = random.getrandbits(16)
        query = self._build_query(host, qtype, txid)

        if self._transport == "tcp":
            try:
                data = self._query_tcp(query, self._dns_port)
                self._ensure_txid(txid, data)
                addrs, ttl_seconds, _truncated = self._parse_response(data, qtype)
                return addrs, ttl_seconds, "tcp", 0
            except (OSError, TimeoutError, ValueError) as exc:
                raise ValueError(
                    self._format_error(host, port, "tcp", exc),
                ) from exc

        try:
            data = self._query_udp(query, self._dns_port)
            self._ensure_txid(txid, data)
            addrs, ttl_seconds, truncated = self._parse_response(data, qtype)
            if truncated:
                raise ValueError("DNS response truncated")
            return addrs, ttl_seconds, "udp", 0
        except (OSError, TimeoutError, ValueError) as udp_exc:
            try:
                data = self._query_tcp(query, self._dns_port)
                self._ensure_txid(txid, data)
                addrs, ttl_seconds, _truncated = self._parse_response(data, qtype)
                return addrs, ttl_seconds, "tcp", 1
            except (OSError, TimeoutError, ValueError) as tcp_exc:
                raise ValueError(
                    self._format_error(host, port, "udp->tcp", tcp_exc, udp_exc),
                ) from tcp_exc

    def _query_udp(self, query: bytes, port: int) -> bytes:
        with socket.socket(self._family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self._timeout_seconds)
            sock.sendto(query, (self._server_ip, port))
            data, _addr = sock.recvfrom(4096)
            return data

    def _query_tcp(self, query: bytes, port: int) -> bytes:
        payload = struct.pack("!H", len(query)) + query
        with socket.socket(self._family, socket.SOCK_STREAM) as sock:
            sock.settimeout(self._timeout_seconds)
            sock.connect((self._server_ip, port))
            sock.sendall(payload)
            length_bytes = self._recv_exact(sock, 2)
            if len(length_bytes) != 2:
                raise ValueError("DNS TCP response length missing")
            length = struct.unpack("!H", length_bytes)[0]
            return self._recv_exact(sock, length)

    @staticmethod
    def _recv_exact(sock: socket.socket, size: int) -> bytes:
        out = bytearray()
        while len(out) < size:
            chunk = sock.recv(size - len(out))
            if not chunk:
                break
            out.extend(chunk)
        if len(out) != size:
            raise ValueError("DNS TCP response truncated")
        return bytes(out)

    @staticmethod
    def _ensure_txid(txid: int, data: bytes) -> None:
        if len(data) < 2:
            raise ValueError("DNS response too short")
        resp_id = struct.unpack("!H", data[:2])[0]
        if resp_id != txid:
            raise ValueError("DNS response transaction ID mismatch")

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
    def _parse_response(data: bytes, qtype: int) -> tuple[list[str], int, bool]:
        if len(data) < 12:
            raise ValueError("DNS response too short")
        _txid, flags, qdcount, ancount, _nscount, _arcount = struct.unpack("!HHHHHH", data[:12])
        offset = 12
        truncated = bool(flags & 0x0200)

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

        return addrs, ttl_min or 0, truncated

    def _format_error(
        self,
        host: str,
        port: int,
        mode: str,
        exc: Exception,
        udp_exc: Exception | None = None,
    ) -> str:
        details = f"{exc}"
        if udp_exc is not None:
            details = f"{udp_exc}; {exc}"
        return (
            "DNS resolve failed "
            f"host={host} port={port} server={self._server_ip} "
            f"dns_port={self._dns_port} transport={mode} error={details}"
        )

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
        self._cache: OrderedDict[
            tuple[str, int],
            tuple[float, tuple[tuple[int, str], ...]],
        ] = OrderedDict()
        if max_entries <= 0:
            logger.debug("dns cache disabled (size=0)")

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
                    self._cache.move_to_end(key, last=True)
                    logger.debug("dns cache hit host=%s port=%d", host, port)
                    trace = _base_dns_trace(self._inner)
                    trace = DnsTrace(
                        dns=trace.dns,
                        cache="hit",
                        transport=trace.transport,
                        fallback=0,
                    )
                    set_dns_trace(trace)
                    return ResolveResult(addrs=list(addrs), ttl_seconds=int(expires_at - now))
                del self._cache[key]
                logger.debug("dns cache expired host=%s port=%d", host, port)
            else:
                logger.debug("dns cache miss host=%s port=%d", host, port)

        result = self._inner.resolve(host, port)
        trace = get_dns_trace()
        if trace is None:
            trace = _base_dns_trace(self._inner)
        set_dns_trace(
            DnsTrace(
                dns=trace.dns,
                cache="miss",
                transport=trace.transport,
                fallback=trace.fallback,
            )
        )
        logger.debug("dns resolved host=%s port=%d addrs=%d", host, port, len(result.addrs))
        ttl_seconds = result.ttl_seconds
        if ttl_seconds > 0:
            ttl_seconds = max(MIN_TTL, min(ttl_seconds, MAX_TTL))
        if ttl_seconds <= 0:
            return result
        expires_at = now + ttl_seconds

        with self._lock:
            if key not in self._cache and len(self._cache) >= self._max_entries:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(
                    "dns cache evict host=%s port=%d",
                    evicted_key[0],
                    evicted_key[1],
                )
            self._cache[key] = (expires_at, tuple(result.addrs))

        return result


def _base_dns_trace(resolver: Resolver) -> DnsTrace:
    if isinstance(resolver, CachingResolver):
        return _base_dns_trace(resolver._inner)
    if isinstance(resolver, PlainDnsResolver):
        return DnsTrace(dns="custom", cache="miss", transport=resolver._transport, fallback=0)
    if isinstance(resolver, SystemResolver):
        return DnsTrace(dns="system", cache="miss", transport="udp", fallback=0)
    return DnsTrace(dns="system", cache="miss", transport="udp", fallback=0)
