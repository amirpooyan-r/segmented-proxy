# SegmentedProxy

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://amirpooyan-r.github.io/segmented-proxy/)

## Start here
Documentation site: https://amirpooyan-r.github.io/segmented-proxy/
About This Project: https://amirpooyan-r.github.io/segmented-proxy/ABOUT_THIS_PROJECT/
Learning Path: https://amirpooyan-r.github.io/segmented-proxy/LEARNING_PATH/

## Project Status / Support
- Educational project (active)
- Python 3.10+
- Not production software
- Issues welcome; best-effort support

## Releases
You can find stable versions and release notes here:

- Latest: https://github.com/amirpooyan-r/segmented-proxy/releases/latest
- History: https://github.com/amirpooyan-r/segmented-proxy/releases

## Overview
SegmentedProxy is a small HTTP/HTTPS proxy made for learning.
It sits between your browser and the internet.
It helps you see how rules and segmentation change traffic.
It is not production software.

## Project Goals
SegmentedProxy is an **educational project** designed to help learners understand
how HTTP/HTTPS proxies, CONNECT tunnels, routing rules, and traffic segmentation
work in practice.

It is **not production software** and is **not intended for censorship bypass,
anonymity, or high-performance use**.

For full details, see:
https://amirpooyan-r.github.io/segmented-proxy/PROJECT_GOALS/


## Documentation Site
Docs are available on GitHub Pages:
https://amirpooyan-r.github.io/segmented-proxy/

## What You Will Learn
- What HTTP and HTTPS are
- How a proxy works between a browser and a server
- What CONNECT tunnels are
- What "segmentation" means in this project (send data in small parts)
- How rules control traffic behavior

## Who Is This Project For?
This project is good for:
- Students
- Beginners learning networking
- People curious about how browsers use proxies

## Quick Start
Step 1: Get the code (Git)
`git clone` downloads a copy of this project to your computer.
Git must be installed.
```bash
git clone git@github.com:amirpooyan-r/segmented-proxy.git
cd segmented-proxy
```

Step 2: Create and activate a virtual environment
Linux/macOS:
```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows cmd:
```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

Step 3: Install the project
```bash
pip install -e .
```

Step 4: Run the proxy
```bash
segproxy --listen-host 127.0.0.1 --listen-port 8080
```

Step 5: Test with curl
```bash
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 https://example.com/
```

Note for Windows users (HTTPS and curl)
When testing HTTPS with `curl` on Windows, you may see
certificate warnings or TLS errors.
This is normal.
SegmentedProxy does not decrypt HTTPS.
It uses a CONNECT tunnel.
The TLS connection is between your client and the website.
Windows `curl` may not trust all certificates by default.
If you only want to test the proxy behavior, you can use:
```bash
curl -k -x http://127.0.0.1:8080 https://example.com/
```

## Learning Path
See the documentation site for a guided learning path:
https://amirpooyan-r.github.io/segmented-proxy/


## Rules and Configuration (Short)
Rules tell the proxy what to do with matching traffic.
A rule can match by host, scheme, method, or path.
Actions can be:
- direct (connect to the server)
- upstream (connect to another proxy)
- block (deny the request)

Segmentation can be:
- none
- fixed (same chunk size)
- random (chunk size changes)

Example rules:
You can pass rules with repeated `--segment-rule` or load a file with `--rules-file`.
Comment lines start with `#` and blank lines are ignored.
See `examples/rules.txt` for a sample rules file you can use with `--rules-file` or copy/paste.
```
example.com=direct
*.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128
*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5
```
If a rule is invalid, SegmentedProxy shows the line number.
It also shows a short reason to help you fix it.

## DNS Resolution

SegmentedProxy needs DNS to connect to remote hosts.

By default, it uses your system DNS resolver and DNS caching is disabled.

Optional DNS features:
- `--dns-cache-size <int>`: enable in-memory DNS cache (use `0` to disable)
- `--dns-server <ip>`: use a specific DNS server (instead of system resolver)
- `--dns-port <int>`: DNS server port (default: `53`)
- `--dns-transport {udp,tcp}`: DNS transport (default: `udp`)

When `udp` is used (default), the proxy will retry DNS over TCP if UDP fails
or the UDP response is truncated.

For full details and examples, see: `docs/DNS_RESOLUTION.md`.

## Limitations
- HTTP/1.1 only
- No TLS decryption. HTTPS is a tunnel.
- Not hardened for production use

## Responsible Use
This project is for learning and testing in places you control.
This is not a bypass guide.
Segmentation does not guarantee bypassing DPI.
Modern networks can still detect and block many techniques.
