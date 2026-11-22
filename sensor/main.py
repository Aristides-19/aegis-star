<<<<<<< HEAD
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
=======
"""Sensor client entry point. Connects to the ship server via TCP and streams
detection events.

Reconnects instead of dying when the ship is not up yet, so ``start.sh`` can
launch all eight sensors without racing the server.
"""

from __future__ import annotations

import argparse
import random
import socket
import sys
import time
from typing import cast

from rich.console import Console
from rich.text import Text

from common.framing import send_msg
from common.protocol import SensorEvent
from common.sectors import SECTOR_MAP, SectorType
from ship import config
from sensor.world import DetectionVal, generate_event


_CONSOLE = Console(highlight=False)


def _say(sector: SectorType, message: str, style: str = "dim") -> None:
    """One coloured line, sector first so the panes line up."""
    _CONSOLE.print(Text.assemble((f" {sector:<2} ", "bold cyan"), (message, style)))


def _connect(sector: SectorType) -> socket.socket | None:
    """Try once. Returns None when the ship is not listening yet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((config.SENSOR_HOST, config.PORT))
    except OSError:
        sock.close()
        return None
    return sock


def _maybe_lie(event: SensorEvent, sector: SectorType) -> SensorEvent:
    """``--alien``: report the opposite of what was detected, flagged as such."""
    if random.random() >= config.ALIEN_LIE_PROBABILITY:
        return event
    flipped: DetectionVal = 0 if event.val == 1 else 1
    return event.model_copy(update={"val": flipped, "origin": "alien"})


def run_sensor(
    sector: SectorType,
    interval: float | None = None,
    once: bool = False,
    force_val: int | None = None,
    alien: bool = False,
) -> None:
    delay = interval if interval is not None else config.SENSOR_INTERVAL
    waiting_announced = False
    seq = 0

    while True:
        sock = _connect(sector)
        if sock is None:
            if not waiting_announced:
                _say(sector, "esperando a la nave...", "dim")
                waiting_announced = True
            time.sleep(config.RECONNECT_DELAY)
            continue

        waiting_announced = False
        _say(sector, f"conectado a {config.SENSOR_HOST}:{config.PORT}", "bold green")
        try:
            while True:
                event = generate_event(sector, seq, force_val=cast(DetectionVal | None, force_val))
                if alien:
                    event = _maybe_lie(event, sector)
                send_msg(sock, event)
                if event.origin == "alien":
                    style = "bold magenta"
                    note = "  MIENTE"
                elif event.val == 1:
                    style = "bold red"
                    note = ""
                else:
                    style = "dim"
                    note = ""
                _say(sector, f"#{seq:<4} enviado   val={event.val}{note}", style)
                seq += 1
                if once:
                    return
                time.sleep(delay)
        except OSError:
            _say(sector, "enlace perdido, reintentando", "bold yellow")
        finally:
            sock.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m sensor.main",
        description="Sensor de un sector: conecta a la nave y reporta detecciones.",
    )
    parser.add_argument("sector", choices=sorted(SECTOR_MAP), help="sector que vigila")
    parser.add_argument("--once", action="store_true", help="enviar un solo evento y salir")
    parser.add_argument("--val", type=int, choices=(0, 1), help="forzar el valor enviado")
    parser.add_argument("--interval", type=float, help="segundos entre envíos")
    parser.add_argument(
        "--alien",
        action="store_true",
        help="simular un sensor capturado: a veces reporta lo contrario",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    sector: SectorType = args.sector
    try:
        run_sensor(
            sector,
            interval=args.interval,
            once=args.once,
            force_val=args.val,
            alien=args.alien,
        )
    except KeyboardInterrupt:
        _say(sector, "detenido", "bold yellow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
>>>>>>> 7b409b7d031ac951c809f2f039e02f6e46475984
