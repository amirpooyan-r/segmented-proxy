# SegmentedProxy

## Overview
SegmentedProxy is an educational HTTP/HTTPS proxy that demonstrates rule-based policy decisions
and traffic segmentation strategies. It focuses on clarity and safe defaults, making it useful for
learning how forward proxies and CONNECT tunnels behave without decrypting TLS traffic.

The proxy supports host-based rules with optional scheme/method/path constraints, plus actions to
direct-connect, forward via an upstream proxy, or block requests. Decisions are explainable via a
score and a concise explanation string to aid debugging and auditing.

## Features
- HTTP forward and CONNECT tunneling
- Actions: `direct` | `upstream` | `block`
- Matching keys: `host_glob`, `scheme`, `method`, `path_prefix`
- Segmentation strategies: `none` | `fixed` | `random`
- Explainable decisions (score + explain string)
- Safe defaults: deny private/reserved addresses; allow/deny lists are supported in settings

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

segproxy --listen-host 127.0.0.1 --listen-port 8080 --log-level INFO
```

Configure your browser to use `127.0.0.1:8080` as an HTTP proxy. Browsers use CONNECT for HTTPS.

Example curl requests:
```bash
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 https://example.com/
```

## Configuration / rules
Rule format:
```
<host_glob>=<mode>[,strategy=none|fixed|random][,chunk=<int>][,min=<int>][,max=<int>][,delay=<int>]
             [,action=direct|upstream|block][,upstream=HOST:PORT][,reason=<text>]
             [,scheme=http|https][,method=<HTTP_METHOD>][,path_prefix=<prefix>]
```

Examples:
```
# Block a tracking host
tracker.example.com=direct,action=block,reason=tracking

# Send traffic to an upstream proxy
*.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128

# Segment only HTTPS CONNECT traffic with random chunk sizes
*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5

# Segment only a specific API path when using an upstream proxy
api.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128,scheme=http,method=POST,path_prefix=/v1/upload,strategy=fixed,chunk=512
```

Precedence rules:
- Higher specificity wins (host glob specificity + scheme/method/path prefix score)
- If scores tie, `block` wins over other actions
- If still tied, earlier rule in the list wins

## Examples
See `examples/rules.txt` for curated rules and `examples/commands.md` for runnable commands.

## Limitations
- HTTP/1.1 only (no HTTP/2)
- No TLS MITM/decryption (CONNECT tunneling only)
- Request Transfer-Encoding is limited (chunked bodies are forwarded verbatim, chunk extensions
  are not interpreted)
- Not production hardened; timeouts and limits exist but the focus is educational

## Responsible use
This project is for education, testing, and debugging in environments where you have permission.
Do not use it to access systems or data without authorization.

## License
This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See the LICENSE file for details.
