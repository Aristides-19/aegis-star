"""Single source of truth for ports, hosts and timing.

Every value can be overridden with an environment variable, which is what
``start.sh`` uses to run the demo on a port that is already free.
"""

from __future__ import annotations

import os

#: Where the ship listens. 0.0.0.0 accepts connections from any interface.
SHIP_HOST: str = os.getenv("AEGIS_SHIP_HOST", "0.0.0.0")

#: Where the sensors connect. Keep in sync with SHIP_HOST for local demos.
SENSOR_HOST: str = os.getenv("AEGIS_SENSOR_HOST", "127.0.0.1")

#: TCP port shared by the ship and every sensor.
PORT: int = int(os.getenv("AEGIS_PORT", "5000"))

#: Backlog passed to listen().
LISTEN_BACKLOG: int = 8

#: Seconds a sensor waits between two reports.
SENSOR_INTERVAL: float = float(os.getenv("AEGIS_SENSOR_INTERVAL", "2.0"))

#: Probability that a generated reading is a detection (1).
DETECTION_PROBABILITY: float = float(os.getenv("AEGIS_DETECTION_PROBABILITY", "0.2"))

#: Seconds a sensor waits before retrying a failed connection.
RECONNECT_DELAY: float = float(os.getenv("AEGIS_RECONNECT_DELAY", "1.0"))

#: The eight sectors, in the order start.sh lays them out.
SECTOR_ORDER: tuple[str, ...] = ("NO", "N", "NE", "E", "SE", "S", "SO", "O")

__all__ = [
    "DETECTION_PROBABILITY",
    "LISTEN_BACKLOG",
    "PORT",
    "RECONNECT_DELAY",
    "SECTOR_ORDER",
    "SENSOR_HOST",
    "SENSOR_INTERVAL",
    "SHIP_HOST",
]
