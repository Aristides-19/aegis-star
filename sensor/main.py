"""Sensor client entry point. Connects to the ship server via TCP and streams detection events."""
import socket
import time
import sys
from typing import cast
from common.framing import send_msg
from common.sectors import SectorType, SECTOR_MAP
from sensor.world import generate_event

def run_sensor(sector: SectorType, host: str = "127.0.0.1", port: int = 5000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print(f"[+] Sensor {sector} conectado a la nave.")
        seq = 0
        while True:
            event = generate_event(sector, seq)
            send_msg(sock, event)
            seq += 1
            time.sleep(2.0)  # Envía reporte cada 2 segundos
    except (socket.error, KeyboardInterrupt):
        print(f"[-] Sensor {sector} desconectado.")
    finally:
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in SECTOR_MAP:
        sectores_validos = ", ".join(SECTOR_MAP.keys())
        print(f"Uso: python -m sensor.main <SECTOR>")
        print(f"Sectores válidos: {sectores_validos}")
        sys.exit(1)
        
    # cast le asegura a Pylance que sys.argv[1] es un SectorType válido
    sector_arg = cast(SectorType, sys.argv[1])
    run_sensor(sector_arg)