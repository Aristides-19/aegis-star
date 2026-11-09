"""Ship entry point: wire the board, the registry and the TCP server together."""

from __future__ import annotations

import signal
import sys

from ship.console import emit
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer


def main() -> int:
    emit("[bold]=== AEGIS-STAR: CENTRO DE MANDO ===[/bold]")

    matrix = ThreatMatrix()
    registry = NodeRegistry()
    server = ShipServer(matrix=matrix, registry=registry)

    def handle_sigint(_sig: int, _frame: object) -> None:
        emit("[*] Apagando sistemas...")
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
