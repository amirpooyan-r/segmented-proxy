# FAQ

## Does SegmentedProxy decrypt HTTPS?
No. It creates a CONNECT tunnel and does not inspect TLS traffic.

## Why does curl show a certificate warning on Windows?
The CONNECT tunnel does not change certificates.
Some tools show warnings differently on Windows, even when the tunnel is normal.

## Is SegmentedProxy a DPI bypass tool?
No. It is for learning and experiments.
Segmentation does not guarantee bypass.

## Why segmentation sometimes does not change anything?
Segmentation only applies when a rule matches the request.
Some servers behave the same, even if the data is segmented.

## When does segmentation apply?
In the current implementation, segmentation applies only to upstream traffic.
If a request goes direct to the server, segmentation is not used.

## How do I load many rules easily?
Use `--rules-file` with a text file:
- One rule per line.
- Blank lines are ignored.
- Lines starting with `#` are comments.

## Why does DNS sometimes use TCP?
DNS uses UDP by default.
If UDP fails or the reply is too large, DNS can fall back to TCP.

## Is DNS cache enabled by default?
No. The default cache size is 0, so caching is off.
Enable it with `--dns-cache-size` and check `cache=hit` or `cache=miss` in `--access-log`.

## Why do I see many logs?
`--access-log` prints one line per request or CONNECT tunnel.
Control verbosity with `--log-level` (for example, `INFO` or `DEBUG`).

## Is this project production-ready?
No. It is educational and experimental.
