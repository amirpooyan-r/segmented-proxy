# Troubleshooting

This page helps you fix common problems when running SegmentedProxy.
It is written for beginners and intermediate learners.

## SegmentedProxy does not start
What it looks like:
- The program exits right away.
- You see a message about binding or permissions.

Possible reasons:
- The port is already in use.
- You try to use a privileged port (below 1024) without permission.
- Your Python version is too old (needs 3.10 or newer).

Steps to fix:
- Choose a free port and try again.
- Use a non-privileged port like 8080.
- Check `python --version` and upgrade if needed.

## Browser cannot load websites
What it looks like:
- The browser shows a loading error.
- Only direct connections work; proxy connections fail.

Possible reasons:
- The proxy is not set correctly in the browser.
- The proxy address or port is wrong.
- A rule blocks the request.

Steps to fix:
- Set the browser proxy to the exact host and port you used for SegmentedProxy.
- Double-check the address (for example `127.0.0.1`) and port.
- Remove or adjust blocking rules and test again.

## HTTPS sites do not work
What it looks like:
- HTTPS pages fail, but HTTP works.
- The browser shows a tunnel or CONNECT error.

Possible reasons:
- HTTPS uses a CONNECT tunnel, and the proxy must accept it.
- A firewall or antivirus blocks CONNECT traffic.
- An upstream proxy is set but unreachable or misconfigured.

Steps to fix:
- Make sure your browser is set to use the proxy for HTTPS.
- Temporarily disable firewall rules that block CONNECT (if safe).
- If you use `action=upstream`, confirm the upstream host and port are correct.

## DNS problems
What it looks like:
- You see "cannot resolve host" errors.
- Names do not resolve, but IPs might work.

Possible reasons:
- DNS resolution fails for the system resolver.
- DNS cache is disabled by default, so each lookup is fresh.
- A custom DNS server or port is wrong.
- UDP DNS is blocked, and TCP fallback may be needed.

Steps to fix:
- Try a known-good hostname to check basic DNS.
- If you set a DNS server, verify the IP and port.
- If UDP is blocked, allow TCP DNS on the same server.
- Read `docs/DNS_RESOLUTION.md` for the exact behavior.

## Rules file problems
What it looks like:
- The program reports a rule parse error.
- A rule matches when it should not, or never matches.

Possible reasons:
- Rule syntax is invalid.
- A key or value is not supported.
- The line has extra spaces or missing parts.
- The example file is copied without the `--segment-rule` flag.

Steps to fix:
- Fix the line reported by SegmentedProxy; it prints the line number.
- Compare your rule to the examples in `examples/rules.txt`.
- Pass each rule with a separate `--segment-rule` flag.
- Keep comments starting with `#` and place rules on their own lines.

## Segmentation does not seem to work
What it looks like:
- Traffic looks normal even with segmentation rules.
- Only some requests seem affected.

Possible reasons:
- Segmentation only applies when a rule matches the request.
- The `segment_upstream` mode only affects the client to upstream path.
- HTTPS uses CONNECT tunnels, HTTP does not.

Steps to fix:
- Check that the host, scheme, method, and path match your rules.
- Use a rule that clearly matches a single host to test.
- Remember that HTTP and HTTPS follow different request paths.

## Logs are confusing
What it looks like:
- Log output is long and hard to follow.
- You are not sure which rule was used.

Possible reasons:
- Default logging is brief and may skip details.
- Debug logs include many internal steps.

Steps to fix:
- Use `--log-level debug` when you want to learn how it works.
- Read logs slowly and look for rule match lines.
- Expect verbose output; it is normal for a learning tool.

## Still stuck?
If you are still stuck, check:
- `README.md`
- `docs/commands.md`
- `docs/DNS_RESOLUTION.md`

Take your time and read the logs slowly.
This project is for learning and testing, not production use.
