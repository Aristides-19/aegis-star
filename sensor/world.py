"""Meteor event generator simulating radar detections for a given sector."""
<<<<<<< HEAD
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
=======

from __future__ import annotations

import random
import time
from typing import Literal

from common.protocol import SensorEvent
from common.sectors import SectorType
from ship import config

DetectionVal = Literal[0, 1]


def generate_event(
    sector: SectorType,
    seq: int,
    force_val: DetectionVal | None = None,
) -> SensorEvent:
    """Build one event. ``force_val`` bypasses the random draw on purpose."""
    val: DetectionVal
    if force_val is not None:
        val = force_val
    else:
        val = 1 if random.random() < config.DETECTION_PROBABILITY else 0
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984

    return SensorEvent(
        type="DETECTION",
        sector=sector,
        val=val,
        timestamp=time.time(),
        seq=seq,
<<<<<<< HEAD
        origin="astro"
    )
=======
        origin="astro",
    )
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
