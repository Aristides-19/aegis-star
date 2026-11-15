<<<<<<< HEAD
"""Thread-safe registry tracking active and offline radar sensor sectors."""
import threading
from common.sectors import SectorType

=======
"""Thread-safe registry tracking which sector nodes are connected."""

from __future__ import annotations

import threading

from common.sectors import SectorType


>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
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

<<<<<<< HEAD
    def get_online(self) -> list[str]:
        with self.lock:
            return sorted(list(self.online_sectors))
=======
    def online(self) -> set[SectorType]:
        """Copy of the connected sectors, safe to read outside the lock."""
        with self.lock:
            return set(self.online_sectors)

    def get_online(self) -> list[SectorType]:
        with self.lock:
            return sorted(self.online_sectors)


__all__ = ["NodeRegistry"]
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
