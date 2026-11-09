"""Live dashboard for the ship.

A fixed layout redrawn in place: the board stays where it is and only the
cells that change are repainted. A log line per event was unreadable at four
events per second.

``Layout`` keeps the proportions, so rich recomputes them when the pane
resizes. All writes go through one lock because eight worker threads call
:meth:`Dashboard.apply` concurrently.
"""

from __future__ import annotations

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
from ship import config

_PRINT_LOCK = threading.Lock()

#: Sector grid as the eye reads it; ``None`` marks the ship cell.
_ROWS: tuple[tuple[SectorType | None, ...], ...] = tuple(
    tuple(
        next((name for name, coord in SECTOR_MAP.items() if coord == (row, col)), None)
        for col in range(3)
    )
    for row in range(3)
)

_SECTORS: tuple[SectorType, ...] = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")

_ALARM_TITLE = "[bold red]ALERTA[/bold red]"
_SAFE_TITLE = "[bold]matriz[/bold]"


class Dashboard:
    """Owns the screen: banner, board, node list and recent events."""

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
            self._console.print(
                "[yellow]stdout no es una terminal: el dashboard necesita un "
                "TTY. Arranca la nave sin pipe ni tee.[/yellow]"
            )
            return
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=8,
            transient=False,
            screen=False,
            vertical_overflow="ellipsis",
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    # -- updates -----------------------------------------------------------
    def apply(self, event: SensorEvent, matrix: Matrix, alert: AlertLevel) -> None:
        with _PRINT_LOCK:
            self._values[event.sector] = event.val
            self._matrix = [list(row) for row in matrix]
            self._alert = alert
            self._events.insert(0, _event_line(event, alert))
            del self._events[self._max_events :]
        self.refresh()

    def set_online(self, online: set[SectorType]) -> None:
        with _PRINT_LOCK:
            self._online = set(online)
        self.refresh()

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render(), refresh=True)

    # -- rendering ---------------------------------------------------------
    def _render(self) -> Layout:
        alarm = self._alert == "RED_ALERT"

        header = Panel(
            Text.assemble(
                ("AEGIS-STAR", "bold"),
                (f" :{config.PORT}", "dim"),
                ("  t+", "dim"),
                (f"{(datetime.now() - self._started).total_seconds():.0f}s  ", "dim"),
                (
                    Text(" ALERTA ROJA ", style="bold white on red")
                    if alarm
                    else Text(" NORMAL ", style="bold black on green")
                ),
            ),
            border_style="red" if alarm else "green",
        )

        nodes = Table.grid(expand=True, padding=(0, 1))
        nodes.add_column(style="bold", width=3)
        nodes.add_column(no_wrap=True)
        nodes.add_column(justify="right", width=3)
        for sector in _SECTORS:
            online = sector in self._online
            nodes.add_row(
                Text(sector, style="cyan" if online else "dim"),
                Text("●" if online else "○", style="green" if online else "yellow"),
                Text("1", style="bold red")
                if self._values[sector] == 1
                else Text("0", style="dim"),
            )

        columns = Table.grid(expand=True)
        columns.add_column(ratio=3)
        columns.add_column(ratio=2)
        columns.add_row(
            Panel(self._board(), title=_ALARM_TITLE if alarm else _SAFE_TITLE,
                  border_style="red" if alarm else "blue"),
            Panel(nodes, title=f"[bold]sensores[/bold] [dim]{len(self._online)}/8[/dim]",
                  border_style="blue"),
        )

        events: RenderableType = (
            Group(*self._events) if self._events else Text("esperando eventos...", style="dim")
        )

        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=3),
            Layout(columns, name="body", size=10),
            Layout(Panel(events, title="[bold]eventos[/bold]", border_style="dim"),
                   name="events", size=self._max_events + 2),
        )
        return layout

    def _board(self) -> Table:
        grid = Table.grid(expand=True)
        for _ in range(3):
            grid.add_column(justify="center", ratio=1)

        for row_index, names in enumerate(_ROWS):
            cells: list[Text] = []
            for col_index, name in enumerate(names):
                if name is None:
                    cells.append(Text("◉ NAVE", style="bold yellow"))
                    continue
                hit = self._matrix[row_index][col_index] == 1
                cells.append(
                    Text(f"█ 1 {name}" if hit else f"· 0 {name}",
                         style="bold red" if hit else "dim")
                )
            grid.add_row(*cells)
        # Pad so the board panel matches the taller node panel.
        for _ in range(len(_SECTORS) - len(_ROWS)):
            grid.add_row(Text(""), Text(""), Text(""))
        return grid


def _event_line(event: SensorEvent, alert: AlertLevel) -> Text:
    hit = event.val == 1
    line = Text()
    line.append(datetime.now().strftime("%H:%M:%S "), style="dim")
    line.append(f"{event.sector:<2} ", style="cyan")
    line.append("DETECTA " if hit else "libre   ", style="bold red" if hit else "dim")
    line.append("→ ", style="dim")
    line.append(alert, style="bold red" if alert == "RED_ALERT" else "bold green")
    return line


__all__ = ["Dashboard"]
