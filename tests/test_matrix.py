"""ThreatMatrix: lock, sequence dedup, heartbeats, concurrent writers."""

from __future__ import annotations

import threading

from common.protocol import SensorEvent
from common.sectors import SECTOR_MAP
from ship.matrix import ThreatMatrix


def event(sector: str, val: int, kind: str = "DETECTION", seq: int = 1) -> SensorEvent:
    return SensorEvent(type=kind, sector=sector, val=val, seq=seq)  # type: ignore[arg-type]


def seqs(*values: int) -> list[int]:
    """Increasing sequence numbers, one per event."""
    return list(range(1, len(values) + 1))


def test_heartbeats_never_touch_the_matrix() -> None:
    matrix = ThreatMatrix()
    assert matrix.apply(event("N", 1, kind="HEARTBEAT")) is False
    assert matrix.snapshot() == ([[0, 0, 0], [0, 0, 0], [0, 0, 0]], "NORMAL")


def test_repeat_write_is_ignored() -> None:
    matrix = ThreatMatrix()
    assert matrix.apply(event("N", 1, seq=1)) is True
    assert matrix.apply(event("N", 1, seq=2)) is False


def test_alert_follows_the_rule() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=1))
    assert matrix.snapshot()[1] == "RED_ALERT"
    matrix.apply(event("E", 1, seq=1))
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
        seq = 0
        for _ in range(500):
            seq += 1
            matrix.apply(event(sector, 1, seq=seq))
            seq += 1
            matrix.apply(event(sector, 0, seq=seq))
        matrix.apply(event(sector, 1, seq=seq + 1))

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
        seq = 0
        while not stop.is_set():
            seq += 1
            matrix.apply(event(sector, 1, seq=seq))
            seq += 1
            matrix.apply(event(sector, 0, seq=seq))

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


# -- sequence dedup --------------------------------------------------------


def test_duplicate_seq_is_dropped() -> None:
    """seq 0, 1, 1, 2: the repeat of 1 must not reach the board."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=0))
    matrix.apply(event("N", 0, seq=1))
    matrix.apply(event("N", 1, seq=1))  # duplicate, must be ignored
    matrix.apply(event("N", 0, seq=2))

    board, _ = matrix.snapshot()
    assert board[0][1] == 0


def test_duplicate_seq_does_not_raise_alert() -> None:
    """A replayed 1 must not flip the board after a later 0 landed."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=5))
    matrix.apply(event("N", 0, seq=6))
    matrix.apply(event("N", 1, seq=5))  # replay of an older event
    assert matrix.snapshot()[1] == "NORMAL"


def test_out_of_order_event_is_dropped() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=10))
    assert matrix.apply(event("N", 0, seq=9)) is False


def test_sequence_is_tracked_per_sector() -> None:
    """Sector E starting at seq 1 is not blocked by sector N reaching seq 9."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=9))
    assert matrix.apply(event("E", 1, seq=1)) is True


def test_heartbeat_advances_the_sequence_without_writing() -> None:
    """A heartbeat is dropped for the board but keeps seq moving."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=1))
    matrix.apply(event("N", 0, kind="HEARTBEAT", seq=2))
    assert matrix.snapshot()[0][0][1] == 1
    # A stale detection after the heartbeat is still refused.
    assert matrix.apply(event("N", 0, seq=1)) is False


def test_forget_lets_a_reconnected_sensor_restart_at_zero() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=7))
    assert matrix.apply(event("N", 0, seq=0)) is False

    matrix.forget("N")

    assert matrix.apply(event("N", 0, seq=0)) is True
    assert matrix.snapshot()[0][0][1] == 0


def test_reset_clears_sequence_history() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=50))
    matrix.reset()
    assert matrix.apply(event("N", 1, seq=0)) is True
