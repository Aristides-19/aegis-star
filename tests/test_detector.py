"""Decision rule: the five assignment states, plus adjacency cases."""

from __future__ import annotations

import pytest

from common.sectors import SECTOR_MAP, SectorType, empty_matrix, neighbors
from ship.detector import classify


def matrix_from(sectors: str) -> list[list[int]]:
    """Build a matrix from a comma-separated sector list, e.g. ``"NE,E"``."""
    matrix = empty_matrix()
    for name in filter(None, (part.strip() for part in sectors.split(","))):
        sector: SectorType = name  # type: ignore[assignment]
        row, col = SECTOR_MAP[sector]
        matrix[row][col] = 1
    return matrix


@pytest.mark.parametrize(
    ("sectors", "expected"),
    [
        ("", "NORMAL"),        # ESTADO 1: sin amenazas
        ("N", "RED_ALERT"),    # ESTADO 2: objeto desde N
        ("NE,E", "NORMAL"),    # ESTADO 3: objeto en la columna este
        ("O", "RED_ALERT"),    # ESTADO 4: objeto desde O
        ("NO", "RED_ALERT"),   # ESTADO 5: objeto desde NO
    ],
)
def test_assignment_states(sectors: str, expected: str) -> None:
    assert classify(matrix_from(sectors)) == expected


@pytest.mark.parametrize(
    ("sectors", "expected"),
    [
        ("NO,N", "NORMAL"),        # touching pair
        ("NO,N,NE", "NORMAL"),     # every detection has a neighbour
        ("NO,N,E,SE", "NORMAL"),   # staircase through the ship corner
        ("NO,N,S,SE", "NORMAL"),   # two pairs, each with a neighbour
        ("NE,E,SO", "RED_ALERT"),  # a pair does not protect a lone SO
        ("NE,SO", "RED_ALERT"),    # opposite corners never touch
        ("N,S", "RED_ALERT"),      # opposite edges, ship between them
        ("NO,NE", "RED_ALERT"),    # share a neighbour but are not adjacent
    ],
)
def test_adjacency_cases(sectors: str, expected: str) -> None:
    assert classify(matrix_from(sectors)) == expected


def test_every_lone_sector_is_red() -> None:
    for sector in SECTOR_MAP:
        assert classify(matrix_from(sector)) == "RED_ALERT", sector


def test_neighbors_share_an_edge_or_a_corner() -> None:
    assert neighbors("N") == {"NO", "NE", "O", "E"}
    assert neighbors("NO") == {"N", "O"}
    assert neighbors("S") == {"O", "SO", "E", "SE"}
    for sector in SECTOR_MAP:
        for other in neighbors(sector):
            assert sector in neighbors(other)
