"""Sensor client entry point. Connects to the ship server via TCP and streams
detection and heartbeat events.
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
from common.rng import stream_for
from common.sectors import SECTOR_MAP, SectorType
from ship import config
from sensor.world import DetectionVal, generate_event

_CONSOLE = Console(highlight=False)


def _say(sector: SectorType, message: str, style: str = "dim") -> None:
    _CONSOLE.print(Text.assemble((f" {sector:<2} ", "bold cyan"), (message, style)))


def _connect(sector: SectorType) -> socket.socket | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((config.SENSOR_HOST, config.PORT))
    except OSError:
        sock.close()
        return None
    return sock


def _maybe_lie(event: SensorEvent, sector: SectorType) -> SensorEvent:
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
    seed: str | None = None,
) -> None:
    delay = interval if interval is not None else config.SENSOR_INTERVAL
    hb_interval = config.HEARTBEAT_INTERVAL
    waiting_announced = False
    seq = 0

    effective_seed = seed or config.SEED
    stream = stream_for(effective_seed, sector) if effective_seed else None

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
            last_detection = 0.0
            last_heartbeat = 0.0
            last_val: DetectionVal = 0

            while True:
                now = time.time()

                # 1. Enviar detección periódica
                if now - last_detection >= delay:
                    event = generate_event(
                        sector,
                        seq,
                        stream=stream,
                        force_val=cast(DetectionVal | None, force_val),
                    )
                    if alien:
                        event = _maybe_lie(event, sector)
                    send_msg(sock, event)
                    last_val = event.val
                    last_detection = now
                    last_heartbeat = now

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

                # 2. Enviar heartbeat periódico si no hubo detección reciente
                elif now - last_heartbeat >= hb_interval:
                    hb_event = SensorEvent(
                        type="HEARTBEAT",
                        sector=sector,
                        val=last_val,
                        timestamp=now,
                        seq=seq,
                        origin="astro",
                    )
                    send_msg(sock, hb_event)
                    last_heartbeat = now
                    _say(sector, f"#{seq:<4} heartbeat val={last_val}", "dim cyan")
                    seq += 1

                time.sleep(0.05)
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
    parser.add_argument("--seed", type=str, help="semilla compartida para el generador PRNG")
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
            seed=args.seed,
        )
    except KeyboardInterrupt:
        _say(sector, "detenido", "bold yellow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())