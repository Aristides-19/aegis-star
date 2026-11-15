"""TCP server for the Ship (Central Command).

Accepts concurrent sensor connections, spawns a dedicated worker thread
per client, frames incoming NDJSON events, and applies detections to the
thread-safe ThreatMatrix.
<<<<<<< HEAD
"""
import socket
import threading
from common.framing import recv_event, ProtocolError
from common.protocol import SensorEvent
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry

class ShipServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5000, matrix: ThreatMatrix | None = None, registry: NodeRegistry | None = None):
        self.host = host
        self.port = port
        self.matrix = matrix
        self.registry = registry
=======

Every console write goes through :mod:`ship.console`, which holds one lock
for the whole block, so eight worker threads cannot shred each other's output.
"""

from __future__ import annotations

import socket
import threading

from common.framing import ProtocolError, recv_event
from ship import config
from ship.console import Dashboard
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry


class ShipServer:
    """Accept loop plus one worker thread per connected sensor."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        matrix: ThreatMatrix | None = None,
        registry: NodeRegistry | None = None,
        dashboard: Dashboard | None = None,
    ) -> None:
        self.host = host if host is not None else config.SHIP_HOST
        self.port = port if port is not None else config.PORT
        self.matrix = matrix if matrix is not None else ThreatMatrix()
        self.registry = registry if registry is not None else NodeRegistry()
        self.dashboard = dashboard if dashboard is not None else Dashboard()
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

<<<<<<< HEAD
    def start(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(8)
        print(f"[*] Ship Server escuchando en {self.host}:{self.port}")
        
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle_sensor, args=(client_sock,), daemon=True)
                t.start()
            except socket.error:
                break

    def _handle_sensor(self, sock: socket.socket):
=======
    def start(self) -> None:
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(config.LISTEN_BACKLOG)
        self.dashboard.start()

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

        self.dashboard.stop()
        self.server_sock.close()

    def stop(self) -> None:
        """Ask the accept loop to exit and wake it up."""
        self.running = False
        try:
            self.server_sock.close()
        except OSError:
            pass

    def _handle_sensor(self, sock: socket.socket) -> None:
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
        buffer = bytearray()
        assigned_sector = None
        try:
            while self.running:
                event = recv_event(sock, buffer)
                if event is None:
<<<<<<< HEAD
                    continue  # Timeout o sin datos inmediatos
                
                # Registrar sector activo
                assigned_sector = event.sector
                if self.registry:
                    self.registry.register(assigned_sector)
                
                # Aplicar detección a la matriz bajo cerrojo
                if self.matrix:
                    self.matrix.apply(event)
                    board, alert = self.matrix.snapshot()
                    print(f"\n[EVENTO RECIBIDO] Sector: {event.sector} | Val: {event.val}")
                    print(f"[ESTADO NAVE] Alerta: {alert}")
                    for row in board:
                        print(" ", row)

        except (socket.error, ProtocolError) as e:
            print(f"[-] Conexión cerrada con sensor {assigned_sector}: {e}")
        finally:
            if assigned_sector and self.registry:
                self.registry.unregister(assigned_sector)
            sock.close()
=======
                    # Either an idle second or the peer closed the socket.
                    # Tell them apart so a closed peer stops the loop.
                    if self._peer_closed(sock):
                        break
                    continue

                assigned_sector = event.sector
                self.registry.register(assigned_sector)

                self.matrix.apply(event)
                board, alert = self.matrix.snapshot()
                self.dashboard.set_online(self.registry.online())
                self.dashboard.apply(event, board, alert)

        except (OSError, ProtocolError):
            pass
        finally:
            if assigned_sector is not None:
                self.registry.unregister(assigned_sector)
                self.dashboard.set_online(self.registry.online())
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
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
