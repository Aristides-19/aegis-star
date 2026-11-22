"""Alien-flagged events: recorded as suspect, never written to the board."""

from __future__ import annotations

from typing import Literal, cast

from common.protocol import EventOrigin, SensorEvent
from common.sectors import SectorType
from ship.matrix import ThreatMatrix

EventType = Literal["DETECTION", "HEARTBEAT"]
DetectionVal = Literal[0, 1]


def event(
    sector: str,
    val: int,
    seq: int = 1,
    origin: str = "astro",
    kind: str = "DETECTION",
) -> SensorEvent:
    return SensorEvent(
        type=cast(EventType, kind),
        sector=cast(SectorType, sector),
        val=cast(DetectionVal, val),
        seq=seq,
        origin=cast(EventOrigin, origin),
    )


def test_alien_event_does_not_write_the_cell() -> None:
    matrix = ThreatMatrix()
    assert matrix.apply(event("N", 1, origin="alien")) is False
    assert matrix.snapshot()[0][0][1] == 0


def test_a_single_alien_sector_cannot_raise_red_alert() -> None:
    """One captured node cannot alarm the ship."""
    matrix = ThreatMatrix()
    for seq in range(1, 6):
        matrix.apply(event("N", 1, seq=seq, origin="alien"))
    assert matrix.snapshot()[1] == "NORMAL"


def test_the_sector_is_marked_suspect() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, origin="alien"))
    assert matrix.suspect() == {"N"}


def test_an_honest_event_from_a_suspect_sector_still_counts() -> None:
    """Being captured once does not disable a node for good."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=1, origin="alien"))
    assert matrix.apply(event("N", 1, seq=2)) is True
    assert matrix.snapshot()[0][0][1] == 1


def test_honest_nodes_are_unaffected_when_no_alien_is_present() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=1))
    matrix.apply(event("E", 1, seq=1))
    assert matrix.suspect() == set()
    assert matrix.snapshot()[1] == "NORMAL"


def test_an_alien_event_still_advances_the_sequence() -> None:
    """A discarded lie still advances the sequence."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 0, seq=5, origin="alien"))
    assert matrix.apply(event("N", 1, seq=4)) is False


def test_forget_clears_the_suspicion_on_reconnect() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, origin="alien"))
    assert matrix.suspect() == {"N"}
    matrix.forget("N")
    assert matrix.suspect() == set()


def test_reset_clears_suspicion() -> None:
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, origin="alien"))
    matrix.reset()
    assert matrix.suspect() == set()


def test_two_alien_sectors_still_cannot_form_a_pair() -> None:
    """Two lies cannot anchor each other."""
    matrix = ThreatMatrix()
    matrix.apply(event("N", 1, seq=1, origin="alien"))
    matrix.apply(event("E", 1, seq=1, origin="alien"))
    board, alert = matrix.snapshot()
    assert not any(map(any, board))
    assert alert == "NORMAL"
    assert matrix.suspect() == {"N", "E"}
