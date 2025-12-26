# SegmentedProxy

SegmentedProxy is an educational HTTP and HTTPS proxy.
It helps you learn how proxies work in real traffic.
It is not production software.

## What it teaches

- HTTP and HTTPS basics
- CONNECT tunnels
- Upstream proxies
- Segmentation strategies
- DNS resolution and caching
- Simple rule matching

## Quick start

Use these steps to run the proxy.
You can skip the dev extras if you want.

1. Clone the repo:
   `git clone https://github.com/amirpooyan-r/segmented-proxy.git`
2. Go into the folder:
   `cd segmented-proxy`
3. Create a virtual env:
   `python -m venv .venv`
4. Install tools and deps:
   `pip install -e ".[dev]"`
   This adds dev tools. The app works without dev extras too.
5. Run the proxy:
   `segproxy --help`
6. Set your browser HTTP proxy to:
   `127.0.0.1:8080` (default)
   HTTPS works via CONNECT through the same proxy.

## Learn more

- [Learning path](LEARNING_PATH.md)
- [How a proxy works](HOW_A_PROXY_WORKS.md)
- [HTTP vs HTTPS](HTTP_VS_HTTPS.md)
- [Segmentation](SEGMENTATION.md)
- [DNS resolution](DNS_RESOLUTION.md)
