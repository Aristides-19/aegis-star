"""Live dashboard for the ship.

The screen is redrawn in place instead of appended to. Printing a block per
event made the output unreadable at four events per second; a fixed layout
that only changes what changed stays readable at any rate.

All rendering goes through one lock, because eight worker threads call
:meth:`Dashboard.refresh` concurrently.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime

from rich.console import Console, Group
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
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=10,
            screen=True,
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
            del self._events[self._max_events :]
        self.refresh()

    def set_online(self, online: set[SectorType]) -> None:
        with _PRINT_LOCK:
            self._online = set(online)
        self.refresh()

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)
            return
        # No TTY (pipe, log file): print the board once per change instead of
        # animating. Still readable, still one block at a time.
        if self._use_live or not self._events:
            return
        board = self._events[0].plain if self._events else ""
        rows = []
        for row_index, names in enumerate(_ROWS):
            cells = []
            for col_index, name in enumerate(names):
                if (row_index, col_index) == SHIP:
                    cells.append(" NAVE ")
                    continue
                cells.append(f" {self._matrix[row_index][col_index]} {name:<2} ")
            rows.append("|".join(cells))
        alarm = "ALERTA ROJA" if self._alert == "RED_ALERT" else "   NORMAL   "
        self._console.print(
            f"[{'red' if self._alert == 'RED_ALERT' else 'green'}]{alarm}[/]  {board}",
            highlight=False,
        )
        for row in rows:
            self._console.print(f"  {row}", highlight=False)

    @staticmethod
    def _event_line(event: SensorEvent, alert: AlertLevel) -> Text:
        line = Text()
        line.append(datetime.now().strftime("%H:%M:%S "), style="dim")
        line.append(f"{event.sector:<2} ", style="cyan")
        if event.val == 1:
            line.append("DETECTA ", style="bold red")
        else:
            line.append("libre   ", style="dim")
        line.append("→ ", style="dim")
        line.append(alert, style="bold red" if alert == "RED_ALERT" else "bold green")
        return line

    # -- rendering ---------------------------------------------------------
    def _render(self) -> Layout:
        root = Layout()
        root.split_column(
            Layout(self._header(), name="header", size=3),
            Layout(self._middle(), name="middle"),
            Layout(self._footer(), name="footer", size=self._max_events + 2),
        )
        return root

    def _header(self) -> Panel:
        uptime = (datetime.now() - self._started).total_seconds()
        alarm = self._alert == "RED_ALERT"
        banner = (
            Text(" ALERTA ROJA · colisión inminente ", style="bold white on red")
            if alarm
            else Text(" NORMAL · tránsito seguro ", style="bold black on green")
        )
        text = Text.assemble(
            ("AEGIS-STAR", "bold"),
            ("  t+", "dim"),
            (f"{uptime:5.1f}s  ", "dim"),
            banner,
        )
        return Panel(text, border_style="red" if alarm else "green", height=3)

    def _middle(self) -> Layout:
        row = Layout()
        row.split_row(
            Layout(self._board_panel(), name="board", ratio=3),
            Layout(self._nodes_panel(), name="nodes", ratio=2),
        )
        return row

    def _board_panel(self) -> Panel:
        grid = Table.grid(expand=True)
        for _ in range(3):
            grid.add_column(justify="center", ratio=1)

        for row_index, names in enumerate(_ROWS):
            if row_index:
                grid.add_row(Text(""), Text(""), Text(""))
            cells: list[Text] = []
            for col_index, name in enumerate(names):
                if (row_index, col_index) == SHIP:
                    cells.append(Text("◉ NAVE", style="bold yellow"))
                    continue
                value = self._matrix[row_index][col_index]
                if value == 1:
                    cells.append(Text(f"█ 1 {name}", style="bold red"))
                else:
                    cells.append(Text(f"· 0 {name}", style="dim"))
            grid.add_row(*cells)

        return Panel(
            grid,
            title="[bold]matriz[/bold] [dim]NO·N·NE / O·★·E / SO·S·SE[/dim]",
            border_style="red" if self._alert == "RED_ALERT" else "blue",
        )

    def _nodes_panel(self) -> Panel:
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(style="bold", width=3)
        grid.add_column(no_wrap=True)
        grid.add_column(justify="right", width=5)

        for sector in _SECTOR_ORDER:
            online = sector in self._online
            value = self._values[sector]
            name = Text(sector, style="cyan" if online else "dim")
            state = (
                Text("en línea", style="green")
                if online
                else Text("sin enlace", style="yellow")
            )
            cell = (
                Text("1", style="bold red")
                if value == 1
                else Text("0", style="dim")
            )
            grid.add_row(name, state, cell)

        busy = sum(1 for sector in _SECTOR_ORDER if sector in self._online)
        return Panel(
            grid,
            title=f"[bold]sensores[/bold] [dim]{busy}/8[/dim]",
            border_style="blue",
        )

    def _footer(self) -> Panel:
        body: Group | Text
        if self._events:
            body = Group(*self._events)
        else:
            body = Text("esperando eventos...", style="dim")
        return Panel(body, title="[bold]eventos[/bold]", border_style="dim")


__all__ = ["Dashboard"]
