"""Sensor client entry point. Connects to the ship server via TCP and streams
detection events.

Reconnects instead of dying when the ship is not up yet, so ``start.sh`` can
launch all eight sensors without racing the server.
"""

from __future__ import annotations

import socket
import sys
import time

from common.framing import send_msg
from common.sectors import SECTOR_MAP, SectorType
from ship import config
from sensor.world import DetectionVal, generate_event


def _as_sector(name: str) -> SectorType:
    """Narrow an already-validated sector name to its literal type."""
    for sector in SECTOR_MAP:
        if sector == name:
            return sector
    raise KeyError(name)


def _checked_val(value: int | None) -> DetectionVal | None:
    """Narrow a CLI integer to the literal type the protocol expects."""
    if value == 1:
        return 1
    if value == 0:
        return 0
    return None


def _connect(sector: SectorType) -> socket.socket | None:
    """Try once. Returns None when the ship is not listening yet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((config.SENSOR_HOST, config.PORT))
    except OSError:
        sock.close()
        return None
    return sock


def run_sensor(
    sector: SectorType,
    interval: float | None = None,
    once: bool = False,
    force_val: int | None = None,
) -> None:
    delay = interval if interval is not None else config.SENSOR_INTERVAL
    waiting_announced = False
    seq = 0

    while True:
        sock = _connect(sector)
        if sock is None:
            if not waiting_announced:
                print(f"[.] sensor {sector}: esperando a la nave...", flush=True)
                waiting_announced = True
            time.sleep(config.RECONNECT_DELAY)
            continue

        waiting_announced = False
        print(f"[+] sensor {sector}: conectado", flush=True)
        try:
            while True:
                send_msg(sock, generate_event(sector, seq, force_val=_checked_val(force_val)))
                seq += 1
                if once:
                    return
                time.sleep(delay)
        except OSError:
            print(f"[-] sensor {sector}: enlace perdido, reintentando", flush=True)
        finally:
            sock.close()


def _parse_args(argv: list[str]) -> tuple[SectorType, float | None, bool, int | None]:
    if not argv or argv[0] not in SECTOR_MAP:
        valid = ", ".join(SECTOR_MAP.keys())
        print("Uso: python -m sensor.main <SECTOR> [--once] [--val 0|1] [--interval S]")
        print(f"Sectores válidos: {valid}")
        raise SystemExit(1)

    sector = _as_sector(argv[0])
    interval = None
    once = False
    force_val = None

    rest = argv[1:]
    index = 0
    while index < len(rest):
        match rest[index]:
            case "--once":
                once = True
            case "--val":
                try:
                    force_val = int(rest[index + 1])
                except (IndexError, ValueError):
                    print("--val necesita 0 o 1")
                    raise SystemExit(1) from None
                index += 1
            case "--interval":
                try:
                    interval = float(rest[index + 1])
                except (IndexError, ValueError):
                    print("--interval necesita un número de segundos")
                    raise SystemExit(1) from None
                index += 1
            case unknown:
                print(f"Opción desconocida: {unknown}")
                raise SystemExit(1)
        index += 1

    return sector, interval, once, force_val


def main(argv: list[str] | None = None) -> int:
    sector, interval, once, force_val = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        run_sensor(sector, interval=interval, once=once, force_val=force_val)
    except KeyboardInterrupt:
        print(f"[-] sensor {sector}: detenido", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
