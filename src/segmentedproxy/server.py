from __future__ import annotations

import logging
import socket
import threading
from contextlib import closing
from typing import Callable, Optional


ClientHandler = Callable[[socket.socket, tuple], None]


class ThreadedTCPServer:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        handler: ClientHandler,
        max_connections: int = 200,
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.handler = handler
        self._sem = threading.BoundedSemaphore(max_connections)
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None

    def serve_forever(self) -> None:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            self._sock = s
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.listen_host, self.listen_port))
            s.listen(128)
            s.settimeout(1.0)  # allow periodic stop checks

            logging.info("Listening on %s:%d", self.listen_host, self.listen_port)

            while not self._stop_event.is_set():
                try:
                    client_sock, client_addr = s.accept()
                except socket.timeout:
                    continue
                except OSError:
                    # socket closed during shutdown
                    break

                if not self._sem.acquire(blocking=False):
                    logging.warning("Too many connections; rejecting %s", client_addr)
                    try:
                        client_sock.close()
                    except Exception:
                        pass
                    continue

                t = threading.Thread(
                    target=self._run_handler,
                    args=(client_sock, client_addr),
                    daemon=True,
                )
                t.start()

            logging.info("Server stopped accepting new connections")

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass

    def _run_handler(self, client_sock: socket.socket, client_addr) -> None:
        try:
            self.handler(client_sock, client_addr)
        except Exception:
            logging.exception("Unhandled error for client %s", client_addr)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            self._sem.release()
