"""Meteor event generator simulating radar detections for a given sector."""
import random
import time
from typing import Literal
from common.protocol import SensorEvent
from common.sectors import SectorType

DetectionVal = Literal[0, 1]

def generate_event(sector: SectorType, seq: int, force_val: DetectionVal | None = None) -> SensorEvent:
    if force_val is not None:
        val: DetectionVal = force_val
    else:
        # Genera 1 con 20% de probabilidad, de lo contrario 0
        val = 1 if random.random() < 0.2 else 0

    return SensorEvent(
        type="DETECTION",
        sector=sector,
        val=val,
        timestamp=time.time(),
        seq=seq,
        origin="astro"
    )