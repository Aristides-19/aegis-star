"""End to end over real TCP: sockets, queue, ticker, matrix.

Uses a free port and a silent dashboard, so it never touches the TUI or the
committed CSV.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest

from typing import Literal, cast

from common.framing import send_msg
from common.protocol import EventOrigin, SensorEvent
from common.sectors import SECTORS, Matrix, SectorType
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer


class SilentDashboard:
    def __init__(self) -> None:
        self.online: set[SectorType] = set()
        self.suspect: set[SectorType] = set()
        self.uncovered: set[SectorType] = set()
        self.events: list[SensorEvent] = []

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def apply(self, event, matrix, alert, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)

    def set_online(self, online, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.online = set(online)

    def set_uncovered(self, uncovered, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.uncovered = set(uncovered)

    def set_suspect(self, suspect, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.suspect = set(suspect)

    def refresh(self) -> None: ...


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def running_ship() -> Iterator[tuple[ShipServer, SilentDashboard, int]]:
    port = free_port()
    dashboard = SilentDashboard()
    server = ShipServer(
        host="127.0.0.1",
        port=port,
        matrix=ThreatMatrix(),
        registry=NodeRegistry(),
        dashboard=dashboard,  # type: ignore[arg-type]
        tick_seconds=0.02,
    )
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.02)

    yield server, dashboard, port

    server.stop()
    thread.join(timeout=3)


DetectionVal = Literal[0, 1]


def event(sector: str, val: int, seq: int = 1, origin: str = "astro") -> SensorEvent:
    return SensorEvent(
        type="DETECTION",
        sector=cast(SectorType, sector),
        val=cast(DetectionVal, val),
        seq=seq,
        origin=cast(EventOrigin, origin),
    )


def send(port: int, *events: SensorEvent) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port))
    for item in events:
        send_msg(sock, item)
    return sock


def settle(server: ShipServer, ticks: int = 4) -> None:
    """Let the ticker run a few times."""
    time.sleep(server.tick_seconds * ticks + 0.05)


def board(server: ShipServer) -> tuple[Matrix, str]:
    matrix, alert = server.matrix.snapshot()
    return matrix, alert


@pytest.mark.parametrize(
    ("sectors", "expected"),
    [
        ((), "NORMAL"),                       # ESTADO 1
        (("N",), "RED_ALERT"),                # ESTADO 2
        (("NE", "E"), "NORMAL"),              # ESTADO 3
        (("O",), "RED_ALERT"),                # ESTADO 4
        (("NO",), "RED_ALERT"),               # ESTADO 5
    ],
)
def test_assignment_states_over_real_sockets(
    running_ship: tuple[ShipServer, SilentDashboard, int],
    sectors: tuple[str, ...],
    expected: str,
) -> None:
    server, _dashboard, port = running_ship
    socks = []
    if sectors:
        for i, sector in enumerate(sectors):
            socks.append(send(port, event(sector, 1, seq=i + 1)))
    else:
        # An empty state still needs one connection to know the ship is up.
        socks.append(socket.create_connection(("127.0.0.1", port)))
    settle(server)
    assert board(server)[1] == expected
    for sock in socks:
        sock.close()


def test_eight_sensors_all_connect(
    running_ship: tuple[ShipServer, SilentDashboard, int],
) -> None:
    server, dashboard, port = running_ship
    socks = [send(port, event(sector, 0, seq=1)) for sector in SECTORS]
    settle(server)
    assert dashboard.online == set(SECTORS)
    for sock in socks:
        sock.close()


def test_duplicate_over_the_wire_is_applied_once(
    running_ship: tuple[ShipServer, SilentDashboard, int],
) -> None:
    server, _dashboard, port = running_ship
    sock = socket.create_connection(("127.0.0.1", port))
    send_msg(sock, event("N", 1, seq=1))
    send_msg(sock, event("N", 1, seq=1))
    send_msg(sock, event("N", 0, seq=2))
    settle(server)
    assert board(server)[0][0][1] == 0
    sock.close()


def test_alien_sensor_cannot_alarm_alone(
    running_ship: tuple[ShipServer, SilentDashboard, int],
) -> None:
    server, dashboard, port = running_ship
    sock = socket.create_connection(("127.0.0.1", port))
    for seq in range(1, 4):
        send_msg(sock, event("N", 1, seq=seq, origin="alien"))
    settle(server)
    assert board(server)[1] == "NORMAL"
    assert dashboard.suspect == {"N"}
    sock.close()


def test_a_disconnect_frees_the_sector_for_a_reconnect(
    running_ship: tuple[ShipServer, SilentDashboard, int],
) -> None:
    """A reconnected sensor counts from seq 0 again."""
    server, dashboard, port = running_ship
    first = send(port, event("N", 1, seq=7))
    settle(server)
    first.close()
    settle(server, ticks=6)
    assert "N" not in dashboard.online

    second = socket.create_connection(("127.0.0.1", port))
    send_msg(second, event("N", 0, seq=0))
    settle(server)
    assert board(server)[0][0][1] == 0
    second.close()
