"""Live dashboard for the ship.

The screen is redrawn in place instead of appended to. Two rules make that
work with rich:

1. The layout must fit the terminal. If it is taller than the window, rich
   cannot repaint in place and every update scrolls, which is worse than a
   plain log. Sizes are therefore derived from ``console.size`` on every
   render, and the dashboard degrades (fewer event lines, then no side panel)
   as the window shrinks.
2. All rendering goes through one lock, because eight worker threads call
   :meth:`Dashboard.refresh` concurrently.
"""

from __future__ import annotations

import shutil
import sys
import threading
from datetime import datetime

from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from common.protocol import AlertLevel, SensorEvent
from common.sectors import SECTOR_MAP, SHIP, Matrix, SectorType

_PRINT_LOCK = threading.Lock()

#: The board as the eye reads it: north on top, west on the left.
_ROWS: tuple[tuple[SectorType, SectorType, SectorType], ...] = (
    ("NO", "N", "NE"),
    ("O", "N", "E"),
    ("SO", "S", "SE"),
)

_SECTOR_ORDER: tuple[SectorType, ...] = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")

#: Rows of chrome that are not the board or the event list.
_FIXED_ROWS = 3 + 2 + 2 + 2 + 2  # header, borders, titles


class Dashboard:
    """Owns the screen: board, alert banner, node list and recent events."""

    def __init__(self, max_events: int = 6, use_live: bool = True) -> None:
        self._max_events = max_events
        self._events: list[Text] = []
        self._online: set[SectorType] = set()
        self._matrix: list[list[int]] = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self._alert: AlertLevel = "NORMAL"
        self._values: dict[SectorType, int] = {sector: 0 for sector in SECTOR_MAP}
        self._started = datetime.now()
        self._console = Console(highlight=False, soft_wrap=False, legacy_windows=False)
        self._live: Live | None = None
        self._use_live = use_live and sys.stdout.isatty()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if not self._use_live:
            self._console.print("[dim]stdout no es una terminal: modo texto[/dim]")
            return
        # transient=False keeps the final frame on screen after stop().
        # screen=False is deliberate: the alternate screen hides the user's
        # scrollback and confuses recording tools. We rely on height fitting
        # the window instead.
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=8,
            transient=False,
            screen=False,
            vertical_overflow="crop",
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    # -- updates -----------------------------------------------------------
    def apply(self, event: SensorEvent, matrix: Matrix, alert: AlertLevel) -> None:
        """Record one event and repaint."""
        with _PRINT_LOCK:
            self._values[event.sector] = event.val
            self._matrix = [list(row) for row in matrix]
            self._alert = alert
            self._events.insert(0, self._event_line(event, alert))
            del self._events[self._event_capacity() :]
        self.refresh()

    def set_online(self, online: set[SectorType]) -> None:
        with _PRINT_LOCK:
            self._online = set(online)
        self.refresh()

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)
            return
        if self._use_live or not self._events:
            return
        self._print_block()

    # -- layout sizing -----------------------------------------------------
    def _height(self) -> int:
        try:
            return self._console.size.height
        except Exception:
            return shutil.get_terminal_size().lines

    def _width(self) -> int:
        try:
            return self._console.size.width
        except Exception:
            return shutil.get_terminal_size().columns

    def _event_capacity(self) -> int:
        """How many event lines fit, given the window height."""
        available = self._height() - _FIXED_ROWS - 5  # board is 5 rows
        return max(0, min(self._max_events, available))

    def _side_by_side(self) -> bool:
        """Below 60 columns the side panel is dropped, not squeezed."""
        return self._width() >= 60

    # -- rendering ---------------------------------------------------------
    def _render(self) -> Layout:
        parts: list[RenderableType] = [self._header()]
        if self._side_by_side():
            row = Layout()
            row.split_row(
                Layout(self._board_panel(), name="board", ratio=3),
                Layout(self._nodes_panel(), name="nodes", ratio=2),
            )
            parts.append(row)
        else:
            parts.append(self._board_panel())

        capacity = self._event_capacity()
        if capacity > 0:
            parts.append(self._footer(capacity))
        return Layout(Group(*parts))

    def _header(self) -> Panel:
        uptime = (datetime.now() - self._started).total_seconds()
        alarm = self._alert == "RED_ALERT"
        banner = (
            Text(" ALERTA ROJA ", style="bold white on red")
            if alarm
            else Text(" NORMAL ", style="bold black on green")
        )
        text = Text.assemble(
            ("AEGIS-STAR", "bold"),
            (" t+", "dim"),
            (f"{uptime:.0f}s  ", "dim"),
            banner,
        )
        return Panel(text, border_style="red" if alarm else "green", height=3)

    def _board_panel(self) -> Panel:
        grid = Table.grid(expand=True)
        for _ in range(3):
            grid.add_column(justify="center", ratio=1)

        for row_index, names in enumerate(_ROWS):
            cells: list[Text] = []
            for col_index, name in enumerate(names):
                if (row_index, col_index) == SHIP:
                    cells.append(Text("◉ NAVE", style="bold yellow"))
                    continue
                value = self._matrix[row_index][col_index]
                label = f"█ 1 {name}" if value == 1 else f"· 0 {name}"
                cells.append(
                    Text(label, style="bold red") if value == 1 else Text(label, style="dim")
                )
            grid.add_row(*cells)

        return Panel(
            grid,
            title=f"[bold]matriz[/bold] [dim]{'ALERTA' if self._alert == 'RED_ALERT' else 'segura'}[/dim]",
            border_style="red" if self._alert == "RED_ALERT" else "blue",
        )

    def _nodes_panel(self) -> Panel:
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(style="bold", width=3)
        grid.add_column(no_wrap=True)
        grid.add_column(justify="right", width=3)

        for sector in _SECTOR_ORDER:
            online = sector in self._online
            value = self._values[sector]
            grid.add_row(
                Text(sector, style="cyan" if online else "dim"),
                Text("●", style="green") if online else Text("○", style="yellow"),
                Text("1", style="bold red") if value == 1 else Text("0", style="dim"),
            )

        return Panel(
            grid,
            title=f"[bold]sensores[/bold] [dim]{len(self._online)}/8[/dim]",
            border_style="blue",
        )

    def _footer(self, capacity: int) -> Panel:
        shown = self._events[:capacity]
        body: Group | Text
        if shown:
            body = Group(*shown)
        else:
            body = Text("esperando eventos...", style="dim")
        return Panel(
            body,
            title="[bold]eventos[/bold]",
            border_style="dim",
            height=capacity + 2,
        )

    # -- event lines -------------------------------------------------------
    @staticmethod
    def _event_line(event: SensorEvent, alert: AlertLevel) -> Text:
        line = Text()
        line.append(datetime.now().strftime("%H:%M:%S "), style="dim")
        line.append(f"{event.sector:<2} ", style="cyan")
        line.append("DETECTA " if event.val == 1 else "libre   ", style="bold red" if event.val == 1 else "dim")
        line.append("→ ", style="dim")
        line.append(alert, style="bold red" if alert == "RED_ALERT" else "bold green")
        return line

    def _print_block(self) -> None:
        """Non-TTY fallback: one compact block per change, grep-friendly."""
        line = self._events[0].plain if self._events else ""
        alarm = "ALERTA ROJA" if self._alert == "RED_ALERT" else "NORMAL     "
        self._console.print(f"{alarm}  {line}", highlight=False)
        for row_index, names in enumerate(_ROWS):
            cells = []
            for col_index, name in enumerate(names):
                if (row_index, col_index) == SHIP:
                    cells.append(" NAVE ")
                    continue
                cells.append(f" {self._matrix[row_index][col_index]} {name:<2} ")
            self._console.print("  " + "|".join(cells), highlight=False)


__all__ = ["Dashboard"]
