"""TCP server for the Ship (Central Command).

Accepts concurrent sensor connections, spawns a dedicated worker thread
per client, frames incoming NDJSON events, and applies detections to the
thread-safe ThreatMatrix.
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
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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
        buffer = bytearray()
        assigned_sector = None
        try:
            while self.running:
                event = recv_event(sock, buffer)
                if event is None:
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