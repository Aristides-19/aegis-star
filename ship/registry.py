"""Thread-safe registry tracking active and offline radar sensor sectors."""
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

    def get_online(self) -> list[str]:
        with self.lock:
            return sorted(list(self.online_sectors))