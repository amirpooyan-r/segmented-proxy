from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


def _normalize_domain_rule(rule: str) -> str:
    r = rule.strip().lower()
    if not r:
        return r
    # Allow ".example.com" suffix rules or exact "example.com"
    return r


def _host_matches_rule(host: str, rule: str) -> bool:
    host = host.lower().strip(".")
    rule = rule.lower().strip()

    if not rule:
        return False

    # Suffix match: ".example.com" matches "a.example.com" and "example.com"
    if rule.startswith("."):
        suffix = rule.lstrip(".")
        return host == suffix or host.endswith("." + suffix)

    # Exact match
    return host == rule


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _is_private_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resolves_to_private(host: str) -> bool:
    # If it's already an IP, check directly
    if _is_ip_literal(host):
        return _is_private_ip(host)

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # DNS failure is handled elsewhere; policy doesn't block on this
        return False

    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            ip = sockaddr[0]
        elif family == socket.AF_INET6:
            ip = sockaddr[0]
        else:
            continue

        if _is_private_ip(ip):
            return True

    return False


def check_host_policy(
    host: str,
    *,
    allow_domains: tuple[str, ...],
    deny_domains: tuple[str, ...],
    deny_private: bool,
) -> PolicyDecision:
    host = host.strip()

    # Deny private networks (best practice)
    if deny_private and _resolves_to_private(host):
        return PolicyDecision(False, "Blocked private/loopback/reserved address")

    # Deny list
    for rule in deny_domains:
        if _host_matches_rule(host, _normalize_domain_rule(rule)):
            return PolicyDecision(False, f"Blocked by deny rule: {rule}")

    # Allow list (if provided)
    if allow_domains:
        for rule in allow_domains:
            if _host_matches_rule(host, _normalize_domain_rule(rule)):
                return PolicyDecision(True, "")
        return PolicyDecision(False, "Not in allow list")

    # Default allow
    return PolicyDecision(True, "")
