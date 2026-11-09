"""Application-layer protocol shared by the ship (server) and the sensors.

FROZEN MODULE -- do not change without updating docs/CONTRACTS.md.

Transport
---------
Plain TCP with newline-delimited JSON (NDJSON): one JSON object per line,
UTF-8 encoded, terminated by ``\\n``. See :mod:`common.framing` for the
wire helpers.

Two message families
--------------------
``SensorEvent``   sensor -> ship   (always)
``UIStateUpdate`` ship   -> UI     (final delivery; not emitted in the MVP)
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from common.sectors import SectorType

#: NORMAL = safe transit, RED_ALERT = imminent collision.
AlertLevel = Literal["NORMAL", "RED_ALERT"]

#: Who produced the reading. ``alien`` is reserved for faulty nodes
#: (final delivery). The field ships now so the JSON never changes shape.
EventOrigin = Literal["astro", "alien"]


class SensorEvent(BaseModel):
    """A message sent from a sensor node to the ship.

    A ``DETECTION`` reports the state of one sector. A ``HEARTBEAT`` keeps the
    node registered on the ship without changing the matrix; both carry
    ``val`` so a heartbeat can also act as "my last reading is ``val``".
    """

    type: Literal["DETECTION", "HEARTBEAT"] = "DETECTION"
    sector: SectorType
    val: Literal[0, 1] = 0
    timestamp: float = Field(default_factory=time.time)
    seq: int = 0
    origin: EventOrigin = "astro"

    @field_validator("timestamp")
    @classmethod
    def _timestamp_is_finite(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("timestamp must be a finite number")
        return value


class NodeStatus(BaseModel):
    """Connection state of one sensor node, as tracked by the ship."""

    sector: SectorType
    online: bool = True
    last_seen: float = Field(default_factory=time.time)
    origin: EventOrigin = "astro"


class UIStateUpdate(BaseModel):
    """Full state snapshot broadcast from the ship to the dashboard.

    Contract for the UI team: every frame is self-contained (the UI never
    reconstructs state by diffing) and ``seq`` increases monotonically so a
    late frame can be discarded.
    """

    matrix: list[list[int]]
    alert_level: AlertLevel = "NORMAL"
    active_nodes: list[str] = Field(default_factory=list)
    offline_nodes: list[str] = Field(default_factory=list)
    seq: int = 0
    ts: float = Field(default_factory=time.time)

    @field_validator("matrix")
    @classmethod
    def _matrix_is_3x3_binary(cls, value: list[list[int]]) -> list[list[int]]:
        if len(value) != 3 or any(len(row) != 3 for row in value):
            raise ValueError("matrix must be 3x3")
        if any(cell not in (0, 1) for row in value for cell in row):
            raise ValueError("matrix cells must be 0 or 1")
        return value


__all__ = [
    "AlertLevel",
    "EventOrigin",
    "NodeStatus",
    "SensorEvent",
    "SectorType",
    "UIStateUpdate",
]
