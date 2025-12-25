# SegmentedProxy

## Overview
SegmentedProxy is a small HTTP/HTTPS proxy made for learning.
It sits between your browser and the internet.
It helps you see how rules and segmentation change traffic.
It is not production software.

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
- docs/LEARNING_PATH.md
- docs/HTTP_VS_HTTPS.md
- docs/HOW_A_PROXY_WORKS.md
- docs/PROJECT_STRUCTURE.md
- docs/SEGMENTATION.md
- docs/GLOSSARY.md
- examples/EXPERIMENTS.md

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
```
example.com=direct
*.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128
*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=random,min=256,max=1024,delay=5
```

## DNS Resolution
The proxy still needs DNS to connect to upstream hosts.
By default it uses your system resolver.
There is an optional in-memory DNS cache to reduce repeated lookups.
Set `--dns-cache-size` to a positive number to enable it.
Use size `0` to disable caching.
The cache uses a fixed TTL for now; later steps will use real DNS TTLs.

## Limitations
- HTTP/1.1 only
- No TLS decryption. HTTPS is a tunnel.
- Not hardened for production use

## Responsible Use
This project is for learning and testing in places you control.
This is not a bypass guide.
Segmentation does not guarantee bypassing DPI.
Modern networks can still detect and block many techniques.
