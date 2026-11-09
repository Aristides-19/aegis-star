"""Ship entry point: wire the dashboard, the board, the registry and the server."""

from __future__ import annotations

import signal
import sys

from rich.console import Console

from ship import config
from ship.console import Dashboard
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer


def main() -> int:
    console = Console()
    console.print(f"[bold]AEGIS-STAR[/bold] · nave escuchando en {config.SHIP_HOST}:{config.PORT}")

    dashboard = Dashboard()
    server = ShipServer(
        matrix=ThreatMatrix(),
        registry=NodeRegistry(),
        dashboard=dashboard,
    )

    def handle_sigint(_sig: int, _frame: object) -> None:
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
