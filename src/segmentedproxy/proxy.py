from __future__ import annotations

import logging
import socket
import threading
from contextlib import closing


class ProxyServer:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        connect_timeout: float = 10.0,
        idle_timeout: float = 60.0,
        max_connections: int = 200,
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.connect_timeout = connect_timeout
        self.idle_timeout = idle_timeout
        self.max_connections = max_connections

        self._sem = threading.BoundedSemaphore(max_connections)

    def serve_forever(self) -> None:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.listen_host, self.listen_port))
            s.listen(128)

            logging.info("Listening on %s:%d", self.listen_host, self.listen_port)

            while True:
                client_sock, client_addr = s.accept()
                if not self._sem.acquire(blocking=False):
                    logging.warning("Too many connections; rejecting %s", client_addr)
                    client_sock.close()
                    continue

                t = threading.Thread(
                    target=self._handle_client_wrapper,
                    args=(client_sock, client_addr),
                    daemon=True,
                )
                t.start()

    def _handle_client_wrapper(self, client_sock: socket.socket, client_addr) -> None:
        try:
            self.handle_client(client_sock, client_addr)
        except Exception:
            logging.exception("Unhandled error for client %s", client_addr)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            self._sem.release()

    def handle_client(self, client_sock: socket.socket, client_addr) -> None:
        logging.info("Client connected: %s", client_addr)
        # TODO: implement HTTP and CONNECT handling next.
