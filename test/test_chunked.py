import socket

from segmentedproxy.main import read_chunked_body


def test_read_chunked_body_roundtrip():
    client, server = socket.socketpair()
    try:
        payload = b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n"

        server.sendall(payload)
        server.shutdown(socket.SHUT_WR)  # 🔴 REQUIRED

        got = read_chunked_body(client)
        assert got == payload
    finally:
        client.close()
        server.close()
