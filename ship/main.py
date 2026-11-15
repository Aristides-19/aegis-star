<<<<<<< HEAD
# ship/main.py
import signal
import sys
=======
"""Ship entry point: wire the dashboard, the board, the registry and the server."""

from __future__ import annotations

import signal
import sys

from ship import config
from ship.console import Dashboard
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer

<<<<<<< HEAD
def main():
    print("=" * 50)
    print("   AEGIS-STAR: CENTRO DE MANDO DE LA NAVE")
    print("=" * 50)

    # 1. Instanciar el estado central protegido por Lock
    matrix = ThreatMatrix()
    registry = NodeRegistry()

    # 2. Instanciar el servidor de sockets multihilo
    server = ShipServer(host="0.0.0.0", port=5000, matrix=matrix, registry=registry)

    # Manejar salida limpia con Ctrl+C
    def handle_sigint(sig, frame):
        print("\n[*] Apagando sistemas de la nave...")
        server.running = False
=======

def main() -> int:
    dashboard = Dashboard()
    server = ShipServer(
        matrix=ThreatMatrix(),
        registry=NodeRegistry(),
        dashboard=dashboard,
    )

    def handle_sigint(_sig: int, _frame: object) -> None:
        server.stop()
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

<<<<<<< HEAD
    # 3. Arrancar el servidor
    try:
        server.start()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
=======
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
