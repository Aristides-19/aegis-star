"""The ticker: batches are applied in a deterministic order."""

from __future__ import annotations

import random

from common.protocol import AlertLevel, SensorEvent
from common.sectors import Matrix
from common.sectors import SECTOR_MAP
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer, order_key


def event(sector: str, val: int, kind: str = "DETECTION", seq: int = 1) -> SensorEvent:
    return SensorEvent(type=kind, sector=sector, val=val, seq=seq)  # type: ignore[arg-type]


class _SilentDashboard:
    """Stand-in for the TUI."""

    def __init__(self) -> None:
        self.events: list[SensorEvent] = []
        self.refreshes = 0

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def apply(self, event, matrix, alert, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)
        if refresh:
            self.refreshes += 1

    def set_online(self, online, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        pass

    def set_suspect(self, suspect, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        pass

    def set_uncovered(self, uncovered, refresh: bool = True) -> None:  # type: ignore[no-untyped-def]
        pass


    def refresh(self) -> None:
        self.refreshes += 1


def server() -> ShipServer:
    return ShipServer(
        matrix=ThreatMatrix(),
        registry=NodeRegistry(),
        dashboard=_SilentDashboard(),  # type: ignore[arg-type]
        tick_seconds=0.01,
    )


def test_order_key_puts_detections_before_heartbeats() -> None:
    detection = event("N", 1, seq=5)
    heartbeat = event("N", 0, kind="HEARTBEAT", seq=6)
    assert order_key(detection) < order_key(heartbeat)


def test_order_key_is_stable_across_runs() -> None:
    events = [event(s, 1, seq=i) for i, s in enumerate(SECTOR_MAP)]
    first = [order_key(e) for e in sorted(events, key=order_key)]
    second = [order_key(e) for e in sorted(reversed(events), key=order_key)]
    assert first == second


def test_shuffled_batch_gives_the_same_board_as_a_sorted_one() -> None:
    """Same events, any arrival order, same board."""

    def run(batch: list[SensorEvent]) -> tuple[Matrix, AlertLevel]:
        srv = server()
        for item in batch:
            srv._queue.put(item)  # the worker would do this
        srv.drain()
        return srv.matrix.snapshot()

    batch = [
        event("N", 1, seq=1),
        event("E", 1, seq=1),
        event("N", 0, seq=2),
        event("O", 1, seq=1),
        event("SE", 1, seq=1),
    ]
    expected = run(batch)
    for seed in range(10):
        shuffled = batch[:]
        random.Random(seed).shuffle(shuffled)
        assert run(shuffled) == expected


def test_one_refresh_per_tick_not_one_per_event() -> None:
    srv = server()
    dashboard = srv.dashboard
    assert isinstance(dashboard, _SilentDashboard)
    for i, sector in enumerate(SECTOR_MAP):
        srv._queue.put(event(sector, 1, seq=i))
    srv.drain()
    assert dashboard.refreshes == 1
    assert len(dashboard.events) == 8


def test_duplicates_inside_one_batch_are_dropped() -> None:
    srv = server()
    srv._queue.put(event("N", 1, seq=1))
    srv._queue.put(event("N", 1, seq=1))
    changed = srv.drain()
    assert changed == 1
    assert srv.matrix.snapshot()[0][0][1] == 1


def test_empty_drain_is_a_no_op() -> None:
    srv = server()
    assert srv.drain() == 0
    assert srv.applied_count() == 0
