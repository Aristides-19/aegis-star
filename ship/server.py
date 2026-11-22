"""TCP server for the Ship (Central Command).

One worker thread per connected sensor frames the incoming NDJSON and puts the
event on a queue. A single ticker thread drains that queue every
``TICK_SECONDS``, sorts the batch, applies it and repaints once.

Workers never touch the board. If they did, the result would depend on which
thread reached the lock first, and two reports in the same millisecond would
land in either order: the same run would not reproduce even with a fixed seed.

Console writes go through :mod:`ship.console`, which holds one lock per block.
"""

from __future__ import annotations

import queue
import socket
import threading

from common.framing import ProtocolError, recv_event
from common.protocol import SensorEvent
from common.sectors import SECTOR_MAP, SectorType
from ship import config
from ship.console import Dashboard
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry

#: Lower sorts first: a detection outranks a heartbeat inside one tick.
_PRIORITY: dict[str, int] = {"DETECTION": 0, "HEARTBEAT": 1}


def order_key(event: SensorEvent) -> tuple[int, int, int]:
    """Sort key for one tick: type, then grid position, then ``seq``.

    The ``seq`` component keeps a sector's events in the order it produced
    them.
    """
    row, col = SECTOR_MAP[event.sector]
    return (_PRIORITY.get(event.type, 9), row * 3 + col, event.seq)


class ShipServer:
    """Accept loop, one worker per sensor, one ticker for the board."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        matrix: ThreatMatrix | None = None,
        registry: NodeRegistry | None = None,
        dashboard: Dashboard | None = None,
        tick_seconds: float | None = None,
    ) -> None:
        self.host = host if host is not None else config.SHIP_HOST
        self.port = port if port is not None else config.PORT
        self.matrix = matrix if matrix is not None else ThreatMatrix()
        self.registry = registry if registry is not None else NodeRegistry()
        self.dashboard = dashboard if dashboard is not None else Dashboard()
        self.tick_seconds = tick_seconds if tick_seconds is not None else config.TICK_SECONDS
        self.running = True

        self._queue: queue.Queue[SensorEvent] = queue.Queue()
        self._stop_ticker = threading.Event()
        self._applied = 0
        self._applied_lock = threading.Lock()

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(config.LISTEN_BACKLOG)
        # Closing a socket does not reliably wake a thread blocked in accept(),
        # so the loop re-checks ``running`` on a timeout instead.
        self.server_sock.settimeout(config.ACCEPT_POLL_SECONDS)
        self.dashboard.start()

        threading.Thread(target=self._tick_loop, daemon=True).start()

        while self.running:
            try:
                client_sock, _addr = self.server_sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_sensor,
                args=(client_sock,),
                daemon=True,
            ).start()

        self._shutdown()

    def stop(self) -> None:
        """Ask the accept loop and the ticker to exit."""
        self.running = False
        self._stop_ticker.set()
        try:
            self.server_sock.close()
        except OSError:
            pass

    def _shutdown(self) -> None:
        self._stop_ticker.set()
        try:
            self.drain()
        except Exception:
            pass
        self.dashboard.stop()
        try:
            self.server_sock.close()
        except OSError:
            pass

    # -- ticker ------------------------------------------------------------
    def _tick_loop(self) -> None:
        """Flush the queue once per tick until stopped."""
        while not self._stop_ticker.wait(self.tick_seconds):
            self.drain()

    def drain(self) -> int:
        """Apply everything queued, then repaint once.

        Returns how many events changed the board.
        """
        expired = self.registry.expire()
        if expired:
            for sector in expired:
                self.matrix.forget(sector)

        batch: list[SensorEvent] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not batch:
            if expired:
                self.dashboard.set_online(self.registry.online(), refresh=True)
            return 0

        batch.sort(key=order_key)
        changed = sum(1 for event in batch if self.matrix.apply(event))

        board, alert = self.matrix.snapshot()
        for event in batch:
            self.dashboard.apply(event, board, alert, refresh=False)
        self.dashboard.set_online(self.registry.online(), refresh=False)
        self.dashboard.set_uncovered(self.registry.uncovered(), refresh=False)
        self.dashboard.set_suspect(self.matrix.suspect(), refresh=False)
        self.dashboard.refresh()

        with self._applied_lock:
            self._applied += changed
        return changed

    def applied_count(self) -> int:
        """Events that changed the board."""
        with self._applied_lock:
            return self._applied

    # -- per-sensor worker -------------------------------------------------
    def _handle_sensor(self, sock: socket.socket) -> None:
        buffer = bytearray()
        assigned_sector: SectorType | None = None
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
                self._queue.put(event)

        except (OSError, ProtocolError):
            pass
        finally:
            if assigned_sector is not None:
                self.registry.unregister(assigned_sector)
                # A sensor that reconnects restarts its counter at zero.
                self.matrix.forget(assigned_sector)
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


__all__ = ["ShipServer", "order_key"]