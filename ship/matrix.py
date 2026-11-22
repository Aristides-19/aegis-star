"""The shared 3x3 threat matrix.

One lock guards the cells. Every write happens inside it; nothing slow (I/O,
logging, callbacks) runs while it is held. Readers get a copy via ``snapshot``.

Cell (1, 1) is the ship: never written, never evaluated.

``apply`` drops an event whose ``seq`` is not newer than the last one accepted
from that sector, so a retransmission cannot be applied twice. ``forget``
clears that history on disconnect, because a sensor that restarts counts from
zero again.

Events flagged ``origin="alien"`` are recorded as suspect and never write a
cell, so one captured sector cannot raise RED_ALERT on its own. An honest
event from that same sector still counts.
"""

from __future__ import annotations

import threading

from common.protocol import AlertLevel, SensorEvent
from common.sectors import SECTOR_MAP, Matrix, SectorType, empty_matrix
from ship import detector


class ThreatMatrix:
    """Thread-safe 3x3 matrix of detections plus the alert decision."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cells: list[list[int]] = empty_matrix()
        self._alert: AlertLevel = "NORMAL"
        self._last_seq: dict[SectorType, int] = {}
        self._suspect: set[SectorType] = set()

    def set_sector(self, sector: SectorType, value: int) -> bool:
        """Write one cell. Returns True if it changed, False on a repeat write."""
        if value not in (0, 1):
            return False
        row, col = SECTOR_MAP[sector]
        with self._lock:
            if self._cells[row][col] == value:
                return False
            self._cells[row][col] = value
            self._alert = detector.classify(self._cells)
            return True

    def apply(self, event: SensorEvent) -> bool:
        """Apply an event, dropping duplicates and out-of-order arrivals.

        Returns True only when the board changed. A heartbeat is accepted for
        its ``seq`` and then ignored. An alien event only marks its sector
        suspect.
        """
        with self._lock:
            last = self._last_seq.get(event.sector)
            if last is not None and event.seq <= last:
                return False
            self._last_seq[event.sector] = event.seq
            if event.origin == "alien":
                self._suspect.add(event.sector)
                return False

        if event.type != "DETECTION":
            return False
        return self.set_sector(event.sector, event.val)

    def forget(self, sector: SectorType) -> None:
        """Drop the history for one sector after a reconnect.

        The sensor restarts at ``seq`` 0 and is presumed honest until it lies
        again.
        """
        with self._lock:
            self._last_seq.pop(sector, None)
            self._suspect.discard(sector)

    def suspect(self) -> set[SectorType]:
        """Sectors that have sent at least one alien-flagged event."""
        with self._lock:
            return set(self._suspect)

    def reset(self) -> None:
        with self._lock:
            self._cells = empty_matrix()
            self._alert = "NORMAL"
            self._last_seq.clear()
            self._suspect.clear()

    def snapshot(self) -> tuple[Matrix, AlertLevel]:
        """Consistent copy of ``(matrix, alert_level)``."""
        with self._lock:
            return [row[:] for row in self._cells], self._alert
