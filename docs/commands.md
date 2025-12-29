# Command-Line Usage

This page is for people who want to run SegmentedProxy using command-line flags.
It focuses on how to start the proxy and what each option means.

## Quick Start
Minimal run (uses default listen host and port):
```bash
segproxy
```

Add one segmentation rule:
```bash
segproxy --segment-rule "*.example.com=segment_upstream,chunk=512,delay=5"
```

Debug logging example:
```bash
segproxy --log-level DEBUG --access-log
```

## Installation / Running
The command is `segproxy`.
It comes from the project’s console script and is available after installation.

## Options Reference
- `-h`, `--help`
  - Default: none
  - Show the help message and exit.

- `--listen-host LISTEN_HOST`
  - Default: `127.0.0.1`
  - IP address to bind the proxy to.
  - Example:
    ```bash
    segproxy --listen-host 0.0.0.0
    ```

- `--listen-port LISTEN_PORT`
  - Default: `8080`
  - TCP port to listen on.
  - Example:
    ```bash
    segproxy --listen-port 8888
    ```

- `--connect-timeout CONNECT_TIMEOUT`
  - Default: `10.0`
  - Maximum time (seconds) to establish upstream connections.

- `--idle-timeout IDLE_TIMEOUT`
  - Default: `60.0`
  - Maximum idle time (seconds) before closing a connection.

- `--max-connections MAX_CONNECTIONS`
  - Default: `200`
  - Maximum number of concurrent connections.

- `--dns-cache-size DNS_CACHE_SIZE`
  - Default: `0`
  - Max entries for DNS cache (0 disables caching).
  - Example:
    ```bash
    segproxy --dns-cache-size 500
    ```

- `--dns-port DNS_PORT`
  - Default: none
  - DNS server port. This requires `--dns-server`.
  - Example:
    ```bash
    segproxy --dns-server 1.1.1.1 --dns-port 53
    ```

- `--dns-transport {udp,tcp}`
  - Default: none
  - DNS transport for `--dns-server` (udp or tcp).
  - Example:
    ```bash
    segproxy --dns-server 1.1.1.1 --dns-transport tcp
    ```

- `--dns-server DNS_SERVER`
  - Default: none
  - Use a specific DNS server (UDP/53) for queries.
  - Example:
    ```bash
    segproxy --dns-server 1.1.1.1
    ```

- `--log-level LOG_LEVEL`
  - Default: `INFO`
  - Set the logging level.
  - Example:
    ```bash
    segproxy --log-level DEBUG
    ```

- `--access-log`
  - Default: off
  - Log one access line per request or CONNECT tunnel.

- `--segmentation {direct,segment_upstream}`
  - Default: `direct`
  - Choose the default segmentation mode.
  - Example:
    ```bash
    segproxy --segmentation segment_upstream
    ```

- `--segment-chunk-size SEGMENT_CHUNK_SIZE`
  - Default: `1024`
  - Default chunk size in bytes when segmentation is used.
  - Example:
    ```bash
    segproxy --segment-chunk-size 512
    ```

- `--segment-delay-ms SEGMENT_DELAY_MS`
  - Default: `0`
  - Default delay (milliseconds) between chunks.
  - Example:
    ```bash
    segproxy --segment-delay-ms 10
    ```

- `--segment-rule SEGMENT_RULE`
  - Default: none (can be repeated)
  - Add a segmentation rule. You can pass this flag multiple times.
  - Example:
    ```bash
    segproxy --segment-rule "*.example.com=segment_upstream,chunk=512,delay=5"
    ```

- `--rules-file RULES_FILE`
  - Default: none (can be repeated)
  - Load rules from a text file (one rule per non-comment line).
  - Example:
    ```bash
    segproxy --rules-file examples/rules.txt
    ```

- `--validate-rules`
  - Default: off
  - Parse and print rule summary, then exit.
  - Example:
    ```bash
    segproxy --rules-file examples/rules.txt --validate-rules
    ```

## Rules Input Patterns
You can provide rules in several ways:
- One rule with a single `--segment-rule` flag.
- Many rules by repeating `--segment-rule`.
- Rules from a file using `--rules-file`.
- You can combine `--segment-rule` and `--rules-file`.

Examples:
```bash
segproxy --segment-rule "example.com=direct"
```

```bash
segproxy \
  --segment-rule "example.com=direct" \
  --segment-rule "*.example.com=segment_upstream,chunk=512,delay=5"
```

```bash
segproxy --rules-file examples/rules.txt --segment-rule "api.example.com=direct"
```

## Common Mistakes
- Port already in use. Choose a different `--listen-port` or stop the other service.
- HTTPS not segmented because `method=CONNECT` is missing from the rule.
- No visible effect because chunks are too large or delay is `0`.
- Wrong quoting on Windows PowerShell vs Bash. If a rule contains `*` or commas, wrap it in quotes.

## Related Pages
- `docs/SEGMENTATION.md`
- `docs/LABS.md`
- `docs/TROUBLESHOOTING.md`
