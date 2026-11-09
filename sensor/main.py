"""Sensor client entry point. Connects to the ship server via TCP and streams
detection events.

Reconnects instead of dying when the ship is not up yet, so ``start.sh`` can
launch all eight sensors without racing the server.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from typing import cast

from rich.console import Console
from rich.text import Text

from common.framing import send_msg
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
                _say(sector, "esperando a la nave...", "dim")
                waiting_announced = True
            time.sleep(config.RECONNECT_DELAY)
            continue

        waiting_announced = False
        _say(sector, f"conectado a {config.SENSOR_HOST}:{config.PORT}", "bold green")
        try:
            while True:
                event = generate_event(sector, seq, force_val=cast(DetectionVal | None, force_val))
                send_msg(sock, event)
                _say(
                    sector,
                    f"#{seq:<4} enviado   val={event.val}",
                    "bold red" if event.val == 1 else "dim",
                )
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    sector: SectorType = args.sector
    try:
        run_sensor(sector, interval=args.interval, once=args.once, force_val=args.val)
    except KeyboardInterrupt:
        _say(sector, "detenido", "bold yellow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
