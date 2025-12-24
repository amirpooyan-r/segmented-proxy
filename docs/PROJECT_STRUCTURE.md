# Project Structure

This section points to the main files in src/segmentedproxy.

## Suggested Reading Order
1. src/segmentedproxy/main.py
2. src/segmentedproxy/server.py
3. src/segmentedproxy/handlers.py
4. src/segmentedproxy/http.py
5. src/segmentedproxy/tunnel.py
6. src/segmentedproxy/segmentation.py
7. src/segmentedproxy/policy.py
8. src/segmentedproxy/net.py

## File Guide

### src/segmentedproxy/main.py
- What it does: CLI entry point. It reads arguments and builds settings.
- Why it exists: to start the proxy with safe defaults.
- When to read it: first.

### src/segmentedproxy/server.py
- What it does: TCP server loop and connection threads.
- Why it exists: to accept clients and pass sockets to handlers.
- When to read it: after main.py.

### src/segmentedproxy/handlers.py
- What it does: handles HTTP forward requests and CONNECT tunnels.
- Why it exists: it is the main request logic.
- When to read it: early, after server.py.

### src/segmentedproxy/http.py
- What it does: parses HTTP requests and builds error replies.
- Why it exists: to keep HTTP parsing simple and focused.
- When to read it: after handlers.py.

### src/segmentedproxy/policy.py
- What it does: allow and deny checks for hosts.
- Why it exists: to block private or denied addresses.
- When to read it: after you see how handlers call policy.

### src/segmentedproxy/segmentation.py
- What it does: rule matching and segmentation decisions.
- Why it exists: to choose direct, upstream, or block actions.
- When to read it: when you study rules and segmentation.

### src/segmentedproxy/tunnel.py
- What it does: relays data between sockets and applies segmentation.
- Why it exists: to build the CONNECT tunnel behavior.
- When to read it: after handlers.py and segmentation.py.

### src/segmentedproxy/net.py
- What it does: small socket helpers for reading data.
- Why it exists: to keep low level networking code in one place.
- When to read it: last.
