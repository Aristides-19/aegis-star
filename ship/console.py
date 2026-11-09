"""Console output for the ship. One lock, so concurrent sensor threads never
interleave their lines.

Every thread prints through :func:`emit`, which holds :data:`_PRINT_LOCK` for
the whole message. Without it the eight worker threads shred each other's
output mid-line, which is exactly what the demo video must not show.
"""

from __future__ import annotations

import threading

from rich.console import Console

from common.protocol import AlertLevel, SensorEvent
from common.sectors import Matrix, SECTOR_MAP, SHIP, SectorType

#: Serializes every write to the console.
_PRINT_LOCK = threading.Lock()

_STDOUT = Console(highlight=False, soft_wrap=True)
_STDERR = Console(stderr=True, highlight=False, soft_wrap=True)

_SECTOR_NAMES: dict[tuple[int, int], str] = {coord: name for name, coord in SECTOR_MAP.items()}


def emit(message: str) -> None:
    """Print one complete line, atomically."""
    with _PRINT_LOCK:
        _STDOUT.print(message)


def emit_error(message: str) -> None:
    """Print one complete error line, atomically."""
    with _PRINT_LOCK:
        _STDERR.print(f"[bold red]{message}[/bold red]")


def render_board(matrix: Matrix) -> str:
    """Draw the 3x3 board as text, with ``x`` for the ship cell."""
    rows = []
    for row_index in range(3):
        cells = []
        for col_index in range(3):
            if (row_index, col_index) == SHIP:
                cells.append("[dim] x [/dim]")
            elif matrix[row_index][col_index] == 1:
                cells.append("[bold red] 1 [/bold red]")
            else:
                cells.append("[dim] 0 [/dim]")
        rows.append("[dim]│[/dim]" + "[dim]│[/dim]".join(cells) + "[dim]│[/dim]")

    header = "[dim]" + " ".join(
        f"{_SECTOR_NAMES.get((0, col), ''):^3}" for col in range(3)
    ) + "[/dim]"
    return header + "\n" + "\n".join(rows)


def render_event(event: SensorEvent, matrix: Matrix, alert: AlertLevel) -> str:
    """One event plus the resulting board, as a single printable block."""
    label = "[bold red]RED_ALERT[/bold red]" if alert == "RED_ALERT" else "[green]NORMAL[/green]"
    return (
        f"[cyan]sensor {event.sector:<2}[/cyan] "
        f"val={event.val} seq={event.seq} "
        f"-> {label}\n"
        f"{render_board(matrix)}"
    )


__all__ = ["emit", "emit_error", "render_board", "render_event"]
