from http.server import BaseHTTPRequestHandler

from test.helpers import free_port, http_via_proxy, sleep_brief, start_http_server, start_proxy


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b"hello-from-origin"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def test_http_get_through_proxy():
    origin_port = free_port()
    proxy_port = free_port()

    httpd = start_http_server(origin_port, HelloHandler)
    proxy = start_proxy(proxy_port, deny_private=False)

    try:
        sleep_brief()
        url = f"http://127.0.0.1:{origin_port}/"
        resp = http_via_proxy(proxy_port, url)
        assert b"200" in resp.split(b"\r\n", 1)[0]
        assert b"hello-from-origin" in resp
    finally:
        proxy.shutdown()
        httpd.shutdown()
