from __future__ import annotations

import logging
import socket

from segmentedproxy.config import Settings
from segmentedproxy.http import HttpRequest, send_http_error, split_absolute_http_url
from segmentedproxy.policy import check_host_policy
from segmentedproxy.segmentation import RequestContext, SegmentationEngine
from segmentedproxy.tunnel import (
    open_upstream,
    parse_connect_target,
    perform_upstream_connect,
    relay_tunnel,
)


def handle_http_forward(
    client_sock: socket.socket,
    req: HttpRequest,
    body: bytes,
    settings: Settings,
) -> None:
    try:
        host, port, path = split_absolute_http_url(req.target)
    except ValueError as e:
        send_http_error(client_sock, 400, str(e))
        return

    headers: dict[str, str] = dict(req.headers)

    # Remove hop-by-hop headers (RFC 7230)
    hop_by_hop = {
        "connection",
        "proxy-connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
    }
    for h in hop_by_hop:
        headers.pop(h, None)

    # If client sent "Connection: x,y", those named headers are hop-by-hop too
    conn_hdr = req.headers.get("connection")
    if conn_hdr:
        for token in conn_hdr.split(","):
            headers.pop(token.strip().lower(), None)

    # --- IMPORTANT: chunked + Content-Length cannot coexist ---
    # We removed "transfer-encoding" from forwarded headers because it's hop-by-hop.
    # But if the request body we are sending is chunked bytes, we must also ensure
    # we don't send Content-Length to the upstream.
    te = req.headers.get("transfer-encoding")
    if te and te.lower() == "chunked":
        headers.pop("content-length", None)

    headers["host"] = host if port == 80 else f"{host}:{port}"
    headers["connection"] = "close"

    policy_decision = check_host_policy(
        host,
        allow_domains=settings.allow_domains,
        deny_domains=settings.deny_domains,
        deny_private=settings.deny_private,
    )
    if not policy_decision.allowed:
        send_http_error(client_sock, 403, f"Forbidden: {policy_decision.reason}")
        return

    engine = SegmentationEngine(settings.segmentation_rules, settings.segmentation_default)
    ctx = RequestContext(
        method=req.method,
        scheme="http",
        host=host,
        port=port,
        path=path,
    )
    decision = engine.decide(ctx)
    policy = decision.policy

    logging.debug(
        "HTTP forward %s:%d %s (action=%s mode=%s strategy=%s)",
        host,
        port,
        path,
        decision.action,
        policy.mode,
        policy.strategy,
    )

    if decision.action == "block":
        reason = decision.reason or "Blocked by segmentation rule"
        send_http_error(client_sock, 403, f"Forbidden: {reason}")
        return

    try:
        if decision.action == "upstream":
            if decision.upstream is None:
                send_http_error(client_sock, 502, "Upstream proxy not configured")
                return
            upstream_host, upstream_port = decision.upstream
            target = _build_absolute_url(host, port, path)
            request_line = f"{req.method} {target} {req.version}\r\n"
            upstream_addr = (upstream_host, upstream_port)
        else:
            request_line = f"{req.method} {path} {req.version}\r\n"
            upstream_addr = (host, port)

        header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        forward = (request_line + header_blob + "\r\n").encode("iso-8859-1")

        with socket.create_connection(upstream_addr, timeout=settings.connect_timeout) as upstream:
            upstream.settimeout(settings.idle_timeout)
            upstream.sendall(forward)
            if body:
                upstream.sendall(body)

            while True:
                data = upstream.recv(4096)
                if not data:
                    break
                client_sock.sendall(data)

    except socket.gaierror:
        send_http_error(client_sock, 502, "DNS resolution failed")
    except TimeoutError:
        send_http_error(client_sock, 504, "Upstream timeout")
    except OSError:
        send_http_error(client_sock, 502, "Upstream connection failed")


def handle_connect_tunnel(
    client_sock: socket.socket,
    target: str,
    settings: Settings,
) -> None:
    try:
        host, port = parse_connect_target(target)
    except Exception:
        send_http_error(client_sock, 400, "CONNECT target must be host:port")
        return

    decision = check_host_policy(
        host,
        allow_domains=settings.allow_domains,
        deny_domains=settings.deny_domains,
        deny_private=settings.deny_private,
    )
    if not decision.allowed:
        send_http_error(client_sock, 403, f"Forbidden: {decision.reason}")
        return

    # Pick segmentation policy for this host
    engine = SegmentationEngine(settings.segmentation_rules, settings.segmentation_default)
    ctx = RequestContext(
        method="CONNECT",
        scheme="https",
        host=host,
        port=port,
        path="",
    )
    decision = engine.decide(ctx)
    policy = decision.policy

    logging.debug(
        "CONNECT tunnel %s:%d (action=%s mode=%s strategy=%s chunk=%d delay_ms=%d)",
        host,
        port,
        decision.action,
        policy.mode,
        policy.strategy,
        policy.chunk_size,
        policy.delay_ms,
    )

    if decision.action == "block":
        reason = decision.reason or "Blocked by segmentation rule"
        send_http_error(client_sock, 403, f"Forbidden: {reason}")
        return

    upstream_host = host
    upstream_port = port
    use_upstream_proxy = False

    if decision.action == "upstream":
        if decision.upstream is None:
            send_http_error(client_sock, 502, "Upstream proxy not configured")
            return
        upstream_host, upstream_port = decision.upstream
        use_upstream_proxy = True

    try:
        upstream = open_upstream(
            upstream_host, upstream_port, settings.connect_timeout, settings.idle_timeout
        )
    except socket.gaierror:
        send_http_error(client_sock, 502, "DNS resolution failed")
        return
    except TimeoutError:
        send_http_error(client_sock, 504, "Upstream timeout")
        return
    except OSError:
        send_http_error(client_sock, 502, "Upstream connection failed")
        return

    if use_upstream_proxy:
        ok = perform_upstream_connect(upstream, host, port, idle_timeout=settings.idle_timeout)
        if not ok:
            send_http_error(client_sock, 502, "Upstream proxy CONNECT failed")
            try:
                upstream.close()
            except Exception:
                pass
            return

    client_sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")

    try:
        relay_tunnel(
            client_sock,
            upstream,
            idle_timeout=settings.idle_timeout,
            policy=policy,
        )
    finally:
        try:
            upstream.close()
        except Exception:
            pass


def _build_absolute_url(host: str, port: int, path: str) -> str:
    if port == 80:
        return f"http://{host}{path}"
    return f"http://{host}:{port}{path}"
