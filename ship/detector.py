"""The decision rule: matrix in, alert level out.

Rule: if any detected sector has no detected neighbour, the object is alone
and heading for the ship -> RED_ALERT. Otherwise every detection is part of a
consecutive group -> NORMAL.
"""

from __future__ import annotations

from common.protocol import AlertLevel
from common.sectors import SECTOR_MAP, Matrix, SectorType, neighbors


def detected_sectors(matrix: Matrix) -> set[SectorType]:
    """Sectors whose cell is 1."""
    return {name for name, (row, col) in SECTOR_MAP.items() if matrix[row][col] == 1}


def classify(matrix: Matrix) -> AlertLevel:
    """RED_ALERT if any detection is isolated, NORMAL otherwise."""
    active = detected_sectors(matrix)
    for sector in active:
        if not active & neighbors(sector):
            return "RED_ALERT"
    return "NORMAL"
