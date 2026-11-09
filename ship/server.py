"""TCP server for the Ship (Central Command).

Accepts concurrent sensor connections, spawns a dedicated worker thread
per client, frames incoming NDJSON events, and applies detections to the
thread-safe ThreatMatrix.

Every console write goes through :mod:`ship.console`, which holds one lock
for the whole block, so eight worker threads cannot shred each other's output.
"""

from __future__ import annotations

import socket
import threading

from common.framing import ProtocolError, recv_event
from ship.console import emit, emit_error, render_event
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry


class ShipServer:
    """Accept loop plus one worker thread per connected sensor."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        matrix: ThreatMatrix | None = None,
        registry: NodeRegistry | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.matrix = matrix if matrix is not None else ThreatMatrix()
        self.registry = registry if registry is not None else NodeRegistry()
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self) -> None:
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(8)
        emit(f"[*] Ship Server escuchando en {self.host}:{self.port}")

        while self.running:
            try:
                client_sock, _addr = self.server_sock.accept()
            except OSError:
                break
            worker = threading.Thread(
                target=self._handle_sensor,
                args=(client_sock,),
                daemon=True,
            )
            worker.start()

        self.server_sock.close()

    def stop(self) -> None:
        """Ask the accept loop to exit and wake it up."""
        self.running = False
        try:
            self.server_sock.close()
        except OSError:
            pass

    def _handle_sensor(self, sock: socket.socket) -> None:
        buffer = bytearray()
        assigned_sector = None
        try:
            while self.running:
                event = recv_event(sock, buffer)
                if event is None:
                    # Either an idle second or the peer closed the socket.
                    # Tell them apart so a closed peer stops the loop.
                    if self._peer_closed(sock):
                        break
                    continue

                assigned_sector = event.sector
                self.registry.register(assigned_sector)

                self.matrix.apply(event)
                board, alert = self.matrix.snapshot()
                emit(render_event(event, board, alert))

        except (OSError, ProtocolError) as exc:
            emit_error(f"[-] Conexión cerrada con sensor {assigned_sector}: {exc}")
        finally:
            if assigned_sector is not None:
                self.registry.unregister(assigned_sector)
                emit_error(f"[-] sensor {assigned_sector} desconectado")
            sock.close()

    @staticmethod
    def _peer_closed(sock: socket.socket) -> bool:
        """True when the socket reports EOF. Does not block."""
        try:
            sock.setblocking(False)
            try:
                data = sock.recv(1)
            finally:
                sock.setblocking(True)
        except BlockingIOError:
            return False
        except OSError:
            return True
        return data == b""


__all__ = ["ShipServer"]
