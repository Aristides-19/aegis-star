"""ThreatMatrix: lock, duplicates, heartbeats, concurrent writers."""

from __future__ import annotations

import threading

from common.protocol import SensorEvent
from common.sectors import SECTOR_MAP
from ship.matrix import ThreatMatrix


def event(sector: str, val: int, kind: str = "DETECTION") -> SensorEvent:
    return SensorEvent(type=kind, sector=sector, val=val)  # type: ignore[arg-type]


def test_heartbeats_never_touch_the_matrix() -> None:
    matrix = ThreatMatrix()
    assert matrix.apply(event("N", 1, kind="HEARTBEAT")) is False
    assert matrix.snapshot() == ([[0, 0, 0], [0, 0, 0], [0, 0, 0]], "NORMAL")


def test_repeat_write_is_ignored() -> None:
    matrix = ThreatMatrix()
    assert matrix.apply(event("N", 1)) is True
    assert matrix.apply(event("N", 1)) is False


def test_alert_follows_the_rule() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1))
    assert matrix.snapshot()[1] == "RED_ALERT"
    matrix.apply(event("E", 1))
    assert matrix.snapshot()[1] == "NORMAL"
    matrix.reset()
    assert matrix.snapshot() == ([[0, 0, 0], [0, 0, 0], [0, 0, 0]], "NORMAL")


def test_snapshot_is_a_copy() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1))
    copy = matrix.snapshot()[0]
    copy[0][1] = 0  # type: ignore[index]
    assert matrix.snapshot()[0][0][1] == 1


def test_concurrent_writers_converge() -> None:
    """Eight threads toggling their own sector: final state must be exact."""
    matrix = ThreatMatrix()

    def worker(sector: str) -> None:
        for _ in range(500):
            matrix.apply(event(sector, 1))
            matrix.apply(event(sector, 0))
        matrix.apply(event(sector, 1))

    threads = [threading.Thread(target=worker, args=(s,)) for s in SECTOR_MAP]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    snapshot, level = matrix.snapshot()
    assert all(
        snapshot[r][c] == (0 if (r, c) == (1, 1) else 1) for r in range(3) for c in range(3)
    )
    assert level == "NORMAL"


def test_snapshot_pair_is_always_consistent() -> None:
    """Readers never see RED_ALERT on an empty matrix."""
    matrix = ThreatMatrix()
    stop = threading.Event()
    bad: list[object] = []

    def writer(sector: str) -> None:
        while not stop.is_set():
            matrix.apply(event(sector, 1))
            matrix.apply(event(sector, 0))

    def reader() -> None:
        while not stop.is_set():
            snapshot, level = matrix.snapshot()
            if level == "RED_ALERT" and not any(map(any, snapshot)):
                bad.append(snapshot)

    threads = [threading.Thread(target=writer, args=(s,)) for s in ("N", "E", "O")]
    threads += [threading.Thread(target=reader) for _ in range(3)]
    for thread in threads:
        thread.start()
    stop.wait(0.5)
    stop.set()
    for thread in threads:
        thread.join()

    assert bad == []
