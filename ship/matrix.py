"""The shared 3x3 threat matrix.

One lock guards the cells. Every write happens inside it; nothing slow (I/O,
logging, callbacks) runs while it is held. Readers get a copy via ``snapshot``.

Cell (1, 1) is the ship: never written, never evaluated.
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
        """Apply a DETECTION event. Heartbeats never change the matrix."""
        if event.type != "DETECTION":
            return False
        return self.set_sector(event.sector, event.val)

    def reset(self) -> None:
        with self._lock:
            self._cells = empty_matrix()
            self._alert = "NORMAL"

    def snapshot(self) -> tuple[Matrix, AlertLevel]:
        """Consistent copy of ``(matrix, alert_level)``."""
        with self._lock:
            return [row[:] for row in self._cells], self._alert
