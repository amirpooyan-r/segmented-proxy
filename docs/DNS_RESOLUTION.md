# DNS Resolution

The proxy needs DNS to connect to remote hosts.
It turns a domain name into an IP address.
Without DNS, the proxy cannot reach upstream servers.

## Default behavior

- The system resolver is used by default.
- DNS cache is disabled by default.

## DNS cache

The cache stores recent DNS results in memory.
It uses TTL from DNS answers when available.
TTL is the time the answer can be reused.

Enable or tune the cache with:
```bash
segproxy --dns-cache-size 512
```

Disable the cache with:
```bash
segproxy --dns-cache-size 0
```

## Custom DNS server

You can set a DNS server IP:
```bash
segproxy --dns-server 1.1.1.1
```

When you set `--dns-server`, real TTL values are used.

## DNS port

The DNS port is 53 by default.
You can change it with:
```bash
segproxy --dns-port 5353
```

## DNS transport

The transport is `udp` by default.
You can choose `udp` or `tcp`:
```bash
segproxy --dns-transport udp
```

```bash
segproxy --dns-transport tcp
```

## UDP to TCP fallback

If you use UDP, the proxy can retry with TCP.
This happens on timeout or network error.
It also happens when the reply is cut short.

If you set TCP, the proxy uses TCP only.
It does not try UDP.

## Examples

Default system DNS and no cache:
```bash
segproxy
```

Cache enabled with system DNS:
```bash
segproxy --dns-cache-size 512
```

Custom DNS server with cache:
```bash
segproxy --dns-server 1.1.1.1 --dns-cache-size 512
```

Custom DNS port:
```bash
segproxy --dns-server 1.1.1.1 --dns-port 5353
```

TCP transport:
```bash
segproxy --dns-server 1.1.1.1 --dns-transport tcp
```

## Troubleshooting

- DNS failures stop outbound connections.
- Try switching between UDP and TCP.
- Check that the server and port are reachable.

## Summary

- The system resolver is the default.
- DNS cache is off unless you enable it.
- `--dns-cache-size 0` turns the cache off.
- `--dns-server` uses plain DNS and real TTL values.
- `--dns-port` changes the DNS port.
- `--dns-transport` selects UDP or TCP.
- UDP can retry with TCP on failure or short replies.
