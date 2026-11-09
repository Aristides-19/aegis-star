# ship/main.py
import signal
import sys
from ship.matrix import ThreatMatrix
from ship.registry import NodeRegistry
from ship.server import ShipServer

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
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # 3. Arrancar el servidor
    try:
        server.start()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()