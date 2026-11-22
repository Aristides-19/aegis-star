"""Meteor event generator simulating radar detections for a given sector."""

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
    stream: random.Random | None = None,
    force_val: DetectionVal | None = None,
) -> SensorEvent:
    """Build one event.

    ``stream`` is the sector's PRNG from :func:`common.rng.stream_for`; without
    it a shared module-level generator is used. ``force_val`` skips the draw.
    """
    val: DetectionVal
    if force_val is not None:
        val = force_val
    else:
        draw = (stream or random).random()
        val = 1 if draw < config.DETECTION_PROBABILITY else 0

    return SensorEvent(
        type="DETECTION",
        sector=sector,
        val=val,
        timestamp=time.time(),
        seq=seq,
        origin="astro",
    )
