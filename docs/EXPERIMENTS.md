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
segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level DEBUG --segment-rule "*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5"
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
