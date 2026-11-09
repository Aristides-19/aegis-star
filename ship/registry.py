"""Thread-safe registry tracking which sector nodes are connected."""

from __future__ import annotations

import threading

from common.sectors import SectorType


class NodeRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.online_sectors: set[SectorType] = set()

    def register(self, sector: SectorType):
        with self.lock:
            self.online_sectors.add(sector)

    def unregister(self, sector: SectorType):
        with self.lock:
            self.online_sectors.discard(sector)

    def online(self) -> set[SectorType]:
        """Copy of the connected sectors, safe to read outside the lock."""
        with self.lock:
            return set(self.online_sectors)

    def get_online(self) -> list[SectorType]:
        with self.lock:
            return sorted(self.online_sectors)


__all__ = ["NodeRegistry"]