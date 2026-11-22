"""Thread-safe registry tracking active and offline radar sensor sectors."""

from __future__ import annotations

import threading
import time

from common.sectors import SECTOR_MAP, SectorType
from ship import config


class NodeRegistry:
    """Tracks online sensors, timestamps of last seen, and coverage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._online: set[SectorType] = set()
        self._last_seen: dict[SectorType, float] = {}

    def register(self, sector: SectorType, now: float | None = None) -> None:
        """Mark a sector online and record timestamp."""
        ts = time.time() if now is None else now
        with self._lock:
            self._online.add(sector)
            self._last_seen[sector] = ts

    def unregister(self, sector: SectorType) -> None:
        """Remove a sector when its connection cleanly closes."""
        with self._lock:
            self._online.discard(sector)
            self._last_seen.pop(sector, None)

    def online(self) -> set[SectorType]:
        """Set of sectors currently connected and alive."""
        with self._lock:
            return set(self._online)

    def uncovered(self) -> set[SectorType]:
        """Set of sectors not currently covered."""
        with self._lock:
            return set(SECTOR_MAP.keys()) - self._online

    def expire(self, now: float | None = None) -> set[SectorType]:
        """Mark offline any sector that has timed out. Returns expired sectors."""
        ts = time.time() if now is None else now
        expired: set[SectorType] = set()
        with self._lock:
            for sector, last in list(self._last_seen.items()):
                if ts - last > config.NODE_TIMEOUT:
                    expired.add(sector)
                    self._online.discard(sector)
                    self._last_seen.pop(sector, None)
        return expired


__all__ = ["NodeRegistry"]