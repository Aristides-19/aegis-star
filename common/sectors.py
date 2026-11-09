"""Geometry of the 3x3 threat matrix.

    +------+------+------+
    |  NO  |  N   |  NE  |
    +------+------+------+
    |  O   | SHIP |  E   |
    +------+------+------+
    |  SO  |  S   |  SE  |
    +------+------+------+

The ship cell (1, 1) is never a detection target.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal, get_args

#: The eight radar sectors.
SectorType = Literal["N", "NE", "E", "SE", "S", "SO", "O", "NO"]

#: A 3x3 board: three rows of three cells. Read-only by contract.
Matrix = Sequence[Sequence[int]]

#: Sector name -> (row, col).
SECTOR_MAP: Final[dict[SectorType, tuple[int, int]]] = {
    "NO": (0, 0), "N": (0, 1), "NE": (0, 2),
    "O": (1, 0),               "E": (1, 2),
    "SO": (2, 0), "S": (2, 1), "SE": (2, 2),
}

_COORD_TO_SECTOR: Final[dict[tuple[int, int], SectorType]] = {
    coord: name for name, coord in SECTOR_MAP.items()
}

#: The cell occupied by the ship.
SHIP: Final[tuple[int, int]] = (1, 1)


def neighbors(sector: SectorType) -> frozenset[SectorType]:
    """Sectors sharing an edge or a corner with ``sector``, ship excluded."""
    row, col = SECTOR_MAP[sector]
    found: set[SectorType] = set()
    for r in (row - 1, row, row + 1):
        for c in (col - 1, col, col + 1):
            if (r, c) != (row, col) and (r, c) in _COORD_TO_SECTOR:
                found.add(_COORD_TO_SECTOR[(r, c)])
    return frozenset(found)


def empty_matrix() -> list[list[int]]:
    """A fresh 3x3 matrix of zeros."""
    return [[0, 0, 0], [0, 0, 0], [0, 0, 0]]


#: Runtime view of ``SectorType``, for validating external input.
SECTORS: Final[tuple[SectorType, ...]] = get_args(SectorType)
