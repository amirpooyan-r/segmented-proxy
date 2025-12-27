# Example commands

## Run the proxy
```bash
segproxy \
  --listen-host 127.0.0.1 \
  --listen-port 8080 \
  --segment-rule "tracker.example.com=direct,action=block,reason=tracking" \
  --segment-rule "*.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128" \
  --segment-rule "*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5"
```

## Access log
Use `--access-log` to print one ACCESS line per request or CONNECT tunnel.

## Rules file
You can load rules from a text file with one rule per line.
Blank lines and lines starting with `#` are ignored.

```bash
segproxy --rules-file examples/rules.txt
```

## Curl through the proxy
```bash
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 https://example.com/
```

## Upstream proxy note
To test `action=upstream`, run a local upstream proxy (for example, Squid) on
`127.0.0.1:3128` and point rules at it. This project does not bundle an upstream
proxy implementation.
