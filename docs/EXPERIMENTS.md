# Experiments

## Before You Start
Run the proxy in one terminal so you can read the logs:
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level DEBUG
```
These logs are examples.
Your exact lines may look a little different.

## 1) HTTP request through the proxy
What to run:
```bash
curl -v -x http://127.0.0.1:8080 http://example.com/
```
What to expect:
- A normal HTTP response.
- No CONNECT step.
What to observe in logs:
- An "HTTP forward" line.
- The chosen action (direct or upstream).
Sample log:
```
DEBUG HTTP forward example.com:80 / (rule=<default> score=-1 action=direct mode=direct strategy=none)
```
What it means:
- The proxy forwarded an HTTP request to the server.
- The default rule was used.

## 2) HTTPS website through CONNECT
What to run:
```bash
curl -v -x http://127.0.0.1:8080 https://example.com/
```
What to expect:
- A CONNECT request and a 200 response from the proxy.
- A TLS handshake after the tunnel is open.
What to observe in logs:
- A "CONNECT tunnel" line.
- The host and port.
Sample log:
```
DEBUG CONNECT tunnel example.com:443 (rule=<default> score=-1 action=direct mode=direct strategy=none chunk=1024 delay_ms=0)
```
What it means:
- The proxy opened a tunnel to the HTTPS server.
- The traffic is encrypted inside the tunnel.

## 3) Block a domain rule
What to run (start the proxy with a rule):
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level DEBUG --segment-rule "example.com=direct,action=block,reason=demo"
```
Then run:
```bash
curl -v -x http://127.0.0.1:8080 http://example.com/
```
What to expect:
- A 403 response from the proxy.
What to observe in logs:
- The rule match and block action.
Sample log:
```
DEBUG HTTP forward example.com:80 / (rule=example.com score=1 action=block mode=direct strategy=none)
```
What it means:
- The block rule matched the host.
- The proxy stopped the request.

## 4) Route traffic via an upstream proxy
This needs another proxy running at 127.0.0.1:3128.
If you do not have one, this test will return 502.
If you do not have an upstream proxy, skip this experiment.

What to run (start the proxy with a rule):
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level DEBUG --segment-rule "*.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128"
```
Then run:
```bash
curl -v -x http://127.0.0.1:8080 http://example.com/
```
What to expect:
- The request goes to the upstream proxy.
What to observe in logs:
- The action is "upstream".
Sample log:
```
DEBUG HTTP forward example.com:80 / (rule=*.example.com score=1 action=upstream mode=segment_upstream strategy=none)
```
What it means:
- The proxy sent the request to the upstream proxy.
It does not connect to the website directly in this step.

## 5) Segment HTTPS CONNECT only
What to run (start the proxy with a rule):
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level DEBUG --segment-rule "*.example.com=segment_upstream,action=direct,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5"
```
Then run:
```bash
curl -v -x http://127.0.0.1:8080 https://example.com/
```
What to expect:
- The page may load a bit slower.
- The tunnel still works.
What to observe in logs:
- The rule match for CONNECT.
- The segmentation strategy and chunk sizes.
Sample log:
```
DEBUG CONNECT tunnel example.com:443 (rule=*.example.com score=3 action=direct mode=segment_upstream strategy=random chunk=1024 delay_ms=5)
```
What it means:
- The proxy segmented the client to upstream flow.
- The chunk sizes were randomized.

## Experiments using --access-log (v0.5.0+)

### Experiment 1: Direct vs Upstream routing
Goal:
- Compare direct routing vs upstream routing using ACCESS lines.

Setup:
- If you want to test upstream, run an upstream proxy on `127.0.0.1:3128`.

Steps:
1) Start the proxy:
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --access-log \
  --segment-rule "example.com=direct" \
  --segment-rule "example.org=segment_upstream,action=upstream,upstream=127.0.0.1:3128"
```
2) Send requests:
```bash
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 http://example.org/
```

What to look for (expected ACCESS fields):
- `rid` should be different for each request.
- `action` should be `direct` for `example.com` and `upstream` for `example.org`.
- `mode` and `strategy` show the policy used.
- If you need the upstream host/port, run with `--log-level debug` and match the same `rid`.

Notes / Troubleshooting:
- If you do not have an upstream proxy, the upstream request will return 502.
- The ACCESS line is still useful for seeing the `action` and `rid`.

### Experiment 2: Segmentation fixed vs none (HTTP body)
Goal:
- See how `strategy=fixed` and `strategy=none` appear in ACCESS lines.

Setup:
- This experiment needs an upstream proxy at `127.0.0.1:3128`.
If you do not have an upstream proxy, skip this experiment.

Steps:
1) Start the proxy with a fixed strategy:
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --access-log \
  --segment-rule "example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128,scheme=http,method=POST,path_prefix=/upload,strategy=fixed,chunk=256"
```
2) Send a POST request:
```bash
curl -x http://127.0.0.1:8080 -X POST --data-binary "hello" http://example.com/upload
```
3) Restart the proxy with `strategy=none` and repeat:
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --access-log \
  --segment-rule "example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128,scheme=http,method=POST,path_prefix=/upload,strategy=none"
```

What to look for (expected ACCESS fields):
- `strategy=fixed` vs `strategy=none`.
- `rid` changes each request.
- The HTTP result may look the same, because segmentation only changes how the body is sent.

Notes / Troubleshooting:
- If you do not have an upstream proxy, you will see 502.
- If you want more detail, add `--log-level debug` and match logs by `rid`.

### Experiment 3: DNS cache + UDP→TCP fallback
Goal:
- Observe DNS cache hits and DNS transport in ACCESS lines.

Setup:
- Use a reachable DNS server (example: `1.1.1.1`).

Steps:
1) Start the proxy with DNS cache:
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080 --access-log \
  --dns-server 1.1.1.1 --dns-transport udp --dns-cache-size 100
```
2) Send the same request twice:
```bash
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 http://example.com/
```
3) To try UDP→TCP fallback, use a network where UDP DNS is blocked,
or a DNS server that blocks UDP but allows TCP.

What to look for (expected ACCESS fields):
- `dns=system` or `dns=custom`.
- `cache=miss` on the first request and `cache=hit` on the second.
- `transport=udp` or `transport=tcp`.
- `fallback=1` only when UDP fails and TCP is used.

Notes / Troubleshooting:
- If you never see `fallback=1`, your UDP queries are working.
- If DNS fails, you may see a 502 error from the proxy.
- Fallback can be hard to reproduce. It is OK to focus on cache miss/hit.

Reminder:
These experiments are for learning.
Logs can be verbose; use `--log-level debug` if needed.
